import sys
import urlparse
import glob
from functools import wraps
import contextlib
import tarfile
import requests
import rollbar
import logging
import subprocess
import os
import json
import click
import urllib3.contrib.pyopenssl
import signal
import pystache
import distutils.spawn
urllib3.contrib.pyopenssl.inject_into_urllib3()

# how is launch used?
# 1. init bar foreground -> /app/bin/ggs foreground
#                        -> foreman start
# 1. init bar command Elixir.Task migrate
# 2. job mix ecto.migrate -> mix ecto.migrate
# 5. upgrade 0.0.2 -> /app/bin/ggs upgrade 0.0.2
# 3. run command Elixir.Task migrate -> /app/bin/ggs command Elixir.Task migrate
# 4. run eval 'Ecto.Migrator.up' -> /app/bin/ggs eval '1+1'
# 6. run remote_console -> /app/bin/ggs remote_console
#                       -> iex --remsh
#
# looks like run is for ssh in and running a command
# job is for creating a new container and running a command
# upgrade sshes in, but downloads a new slug and all that before running a command

# changing it to?
# strategy? pass into launch a class/function to run for run
# 2. job mix ecto.migrate -> mix ecto.migrate
# 2. distillery_job command Elixir.Task migrate -> mix ecto.migrate
# leave upgrade as-is
# leave init as-is
#
# command         log_shuttle use_procfile is_distillery done?
# init(mix)       True        True         False         first pass
# init(distillery)True        True         True          first pass
# run(mix)        False       False        False         first pass
# run(distillery) False       False        True          first pass
# job             True        False        False         first pass
# upgrade         True        False        True          first pass
# distillery_job  True        False        True          first pass
# bootstrap       N/A         N/A          N/A, but True

@click.group()
@click.option('--env', envvar='GIGALIXIR_ENV', default='prod', help="GIGALIXIR environment [prod, dev].")
@click.pass_context
def cli(ctx, env):
    ctx.obj = {}
    ROLLBAR_POST_CLIENT_ITEM = "2413770c24624d498a9baa91d15f7ece"
    if env == "prod":
        rollbar.init(ROLLBAR_POST_CLIENT_ITEM, 'production', enabled=True)
        host = "https://api.gigalixir.com"
    elif env == "dev":
        rollbar.init(ROLLBAR_POST_CLIENT_ITEM, 'development', enabled=False)
        host = "http://localhost:4000"
    else:
        raise Exception("Invalid GIGALIXIR_ENV")

    ctx.obj['host'] = host

def report_errors(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        try:
            f(*args, **kwds)
        except SystemExit:
            raise
        except:
            rollbar.report_exc_info()
            raise
    return wrapper

@cli.command()
@click.argument('repo', nargs=1)
@click.argument('cmd', nargs=-1)
@click.option('--app_key', envvar='APP_KEY', default=None)
@click.option('--logplex_token', envvar='LOGPLEX_TOKEN', default=None)
@click.option('--erlang_cookie', envvar='ERLANG_COOKIE', default=None)
@click.option('--ip', envvar='MY_POD_IP', default=None)
@click.pass_context
@report_errors
def init(ctx, repo, cmd, app_key, logplex_token, erlang_cookie, ip):
    if app_key == None:
        raise Exception("APP_KEY not found.")

    start_ssh(repo, app_key)

    release = current_release(ctx.obj['host'], repo, app_key)
    slug_url = release["slug_url"]
    customer_app_name = release["customer_app_name"]

    persist_env(repo, customer_app_name, app_key, logplex_token, erlang_cookie, ip)

    download_file(slug_url, "/app/%s.tar.gz" % customer_app_name)
    extract_file('/app', '%s.tar.gz' % customer_app_name)
    maybe_start_epmd()

    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        log_start_and_stop_web(logplex_token, repo, hostname)
        load_profile()
        if is_distillery(customer_app_name):
            maybe_use_default_vm_args()
        ps = foreman_start(customer_app_name, cmd)
        pipe_to_log_shuttle(ps, cmd, logplex_token, repo, hostname)
        ps.wait()

    launch(ctx, exec_fn, repo, app_key, ip=ip, release=release)

def persist_env(repo, customer_app_name, app_key, logplex_token, erlang_cookie, ip):
    # HACK ALERT 
    # Save important env variables for observer and run-cmd when it SSHes in.
    # Normally these variables are set by the pod spec and injected by kubernetes, but 
    # if you SSH into the container manually, they are not set.
    # On container startup, we save these variables to the filesystem for use later when
    # you SSH in.
    kube_var_path = "/kube-env-vars"
    if not os.path.exists(kube_var_path):
        os.makedirs(kube_var_path)
    with open('%s/MY_POD_IP' % kube_var_path, 'w') as f:
        f.write(os.environ['MY_POD_IP'])
    with open('%s/ERLANG_COOKIE' % kube_var_path, 'w') as f:
        f.write(os.environ[ 'ERLANG_COOKIE' ])
    with open('%s/REPO' % kube_var_path, 'w') as f:
        f.write(repo)
    with open('%s/APP' % kube_var_path, 'w') as f:
        f.write(customer_app_name)
    with open('%s/APP_KEY' % kube_var_path, 'w') as f:
        f.write(app_key)
    with open('%s/LOGPLEX_TOKEN' % kube_var_path, 'w') as f:
        f.write(os.environ[ 'LOGPLEX_TOKEN' ])

def extract_file(folder, filename):
    with cd(folder):
        tar = tarfile.open(filename, "r:gz")
        tar.extractall()
        tar.close()

def maybe_start_epmd():
    epmd_path = find('epmd', '/app')
    if epmd_path:
        os.symlink(epmd_path, '/usr/local/bin/epmd')

# DEPRECATED: we just use job now and require the user to pass in bin/app command <mod> <fun>
# used by the old gigalixir run that won't be available soon. delete this once giglaixir run is changed.
@cli.command()
@click.argument('cmd', nargs=-1)
@click.pass_context
@report_errors
def distillery_job(ctx, cmd):
    repo = load_env_var('REPO')
    app_key = load_env_var('APP_KEY')
    release = current_release(ctx.obj['host'], repo, app_key)
    slug_url = release["slug_url"]
    customer_app_name = release["customer_app_name"]

    download_file(slug_url, "/app/%s.tar.gz" % customer_app_name)
    extract_file('/app', '%s.tar.gz' % customer_app_name)

    if not is_distillery(customer_app_name):
        raise Exception("This can only be done on a distillery release.")

    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        log(logplex_token, repo, hostname, "Attempting to run 'bin/%s %s' in a new container." % (customer_app_name, ' '.join(cmd)))
        load_profile()
        maybe_use_default_vm_args()
        ps = distillery_command(customer_app_name, cmd, logplex_token, repo, hostname)
        pipe_to_log_shuttle(ps, cmd, logplex_token, repo, hostname)
        ps.wait()

    launch(ctx, exec_fn, repo, app_key, release=release)

@cli.command()
@click.argument('cmd', nargs=-1)
@click.pass_context
@report_errors
def shell(ctx, cmd):
    repo = load_env_var('REPO')
    app_key = load_env_var('APP_KEY')
    ip = load_env_var('MY_POD_IP')
    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        if is_distillery(customer_app_name):
            maybe_use_default_vm_args()
        shell_command_exec(cmd, ip, logplex_token, repo, hostname)
    launch(ctx, exec_fn, repo, app_key, ip=ip)

@cli.command()
@click.argument('cmd')
@click.pass_context
@report_errors
def distillery_eval(ctx, cmd):
    customer_app_name = load_env_var('APP')
    if not is_distillery(customer_app_name):
        raise Exception("This can only be done on a distillery release.")

    repo = load_env_var('REPO')
    app_key = load_env_var('APP_KEY')
    ip = load_env_var('MY_POD_IP')
    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        maybe_use_default_vm_args()
        # we choose eval or rpc depending on if we are running distillery 2.0 or not.
        # really, we check the capabilities of the release. if distillery.eval == elixir then
        # we use rpc. eval does not run on the existing node. it tries to spin up a new "minimal" node
        # which does not seem to have the repo running. this means that migrations don't work, the cookie
        # and node name are potentially incorrect.
        #
        # current_release *could* be wrong. if you deployed, but this is run on an old container before it
        # is terminated.
        release = current_release(ctx.obj['host'], repo, app_key)
        capabilities = release.get("capabilities")
        eval_language = "erlang"
        # some kind of monad usable here?
        if capabilities:
            dist = capabilities.get("distillery")
            if dist:
                eval_language = dist.get("eval")
        
        if eval_language == "elixir":
            eval_command = "rpc"
        else:
            eval_command = "eval"

        distillery_command_exec(customer_app_name, [eval_command, cmd])
    launch(ctx, exec_fn, repo, app_key, ip=ip)

@cli.command()
@click.pass_context
@report_errors
def remote_console(ctx):
    repo = load_env_var('REPO')
    app_key = load_env_var('APP_KEY')
    ip = load_env_var('MY_POD_IP')
    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        if is_distillery(customer_app_name):
            maybe_use_default_vm_args()
            distillery_command_exec(customer_app_name, ["remote_console"])
        else:
            os.execvp('iex', ['iex', '--name', 'remsh@%s' % ip, '--cookie', os.environ['MY_COOKIE'], '--remsh', os.environ['MY_NODE_NAME']])
    launch(ctx, exec_fn, repo, app_key, ip=ip)

@cli.command()
@click.argument('cmd', nargs=-1)
@click.pass_context
@report_errors
def job(ctx, cmd):
    repo = load_env_var('REPO')
    app_key = load_env_var('APP_KEY')
    release = current_release(ctx.obj['host'], repo, app_key)
    slug_url = release["slug_url"]
    customer_app_name = release["customer_app_name"]

    download_file(slug_url, "/app/%s.tar.gz" % customer_app_name)
    extract_file('/app', '%s.tar.gz' % customer_app_name)

    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        log(logplex_token, repo, hostname, "Attempting to run '%s' in a new container." % (' '.join(cmd)))
        load_profile()
        if is_distillery(customer_app_name):
            maybe_use_default_vm_args()
        ps = shell_command(cmd, logplex_token, repo, hostname)
        pipe_to_log_shuttle(ps, cmd, logplex_token, repo, hostname)
        ps.wait()

    launch(ctx, exec_fn, repo, app_key, release=release)

# DEPRECATED: this does too much and does different things depending on mix vs distillery. 
# it is used by the old gigalixir remote_console, gigalixir ssh <cmd>, gigalixir distillery <cmd>
# gigalixir observer's eval for cookie and node name, gigalixir migrate uses eval
# 
# we are moving remote_console over to a dedicated command.
# we are moving ssh to not use gigalixir_run at all
# we are removing distillery completely
# we are moving eval over to it's own command
@cli.command()
@click.argument('cmd', nargs=-1)
@click.pass_context
@report_errors
def run(ctx, cmd):
    repo = load_env_var('REPO')
    app_key = load_env_var('APP_KEY')
    ip = load_env_var('MY_POD_IP')
    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        if is_distillery(customer_app_name):
            maybe_use_default_vm_args()
            distillery_command_exec(customer_app_name, cmd)
        else:
            shell_command_exec(cmd, ip, logplex_token, repo, hostname)
    launch(ctx, exec_fn, repo, app_key, ip=ip)

def generate_vmargs(node_name, cookie):
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    rel_path = "templates/vm.args.mustache"
    template_path = os.path.join(script_dir, rel_path)
    vmargs_path = "/release-config/vm.args"

    with open(template_path, "r") as f:
        template = f.read()
        vmargs = pystache.render(template, {"MY_NODE_NAME": node_name, "MY_COOKIE": cookie})
        with open(vmargs_path, "w") as g:
            g.write(vmargs)

@cli.command()
@click.argument('customer_app_name', nargs=1)
@click.argument('slug_url', nargs=1)
@click.argument('cmd', nargs=-1)
@click.pass_context
@report_errors
def bootstrap(ctx, customer_app_name, slug_url, cmd):
    # Similar to init except does not ask api.gigalixir.com for the current slug url or configs.
    # This also does not support SSH, observer, etc.
    # Used mainly for debugging and manual emergency deploys
    download_file(slug_url, "/app/%s.tar.gz" % customer_app_name)
    extract_file("/app", "%s.tar.gz" % customer_app_name)
    with cd('/app'):
        os.execv('/app/bin/%s' % customer_app_name, ['/app/bin/%s' % customer_app_name] + list(cmd))

@cli.command()
@click.argument('version')
@click.pass_context
@report_errors
def upgrade(ctx, version):
    app = load_env_var('APP')
    repo = load_env_var('REPO')
    app_key = load_env_var('APP_KEY')
    release = current_release(ctx.obj['host'], repo, app_key)
    slug_url = release["slug_url"]
    config = release["config"]
    customer_app_name = release["customer_app_name"]

    if not is_distillery(customer_app_name):
        raise Exception("This can only be done on a distillery release.")

    # get mix version from slug url. 
    # TODO: make this explicit in the database.
    # https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz
    mix_version = urlparse.urlparse(slug_url).path.split('/')[5]

    release_dir = "/app/releases/%s" % mix_version
    if not os.path.exists(release_dir):
        os.makedirs(release_dir)

    download_file(slug_url, "/app/releases/%s/%s.tar.gz" % (mix_version, app))
    extract_file("/app/releases/%s" % mix_version, '%s.tar.gz' % customer_app_name)

    def exec_fn(logplex_token, customer_app_name, repo, hostname):
        log(logplex_token, repo, hostname, "Attempting to upgrade '%s' on host '%s'\n" % (repo, hostname))
        cmd = ('upgrade', mix_version)
        maybe_use_default_vm_args()
        ps = distillery_command(customer_app_name, cmd, logplex_token, repo, hostname)
        pipe_to_log_shuttle(ps, cmd, logplex_token, repo, hostname)
        ps.wait()

    launch(ctx, exec_fn, repo, app_key, release=release)


def load_configs(release):
    config = release["config"]
    os.environ['LC_ALL'] = "en_US.UTF-8"
    for key, value in config.iteritems():
        os.environ[key] = value

# is this really needed? all it does it load up env vars
def launch(ctx, exec_fn, repo, app_key, ip=None, release=None):
    # should this come from current_release or set as env var? only repo and app_key are 
    # needed to fetch the current release.
    logplex_token = load_env_var('LOGPLEX_TOKEN')

    release = release or current_release(ctx.obj['host'], repo, app_key)
    customer_app_name = release["customer_app_name"]
    hostname = get_hostname()

    # iex --remsh uses MY_NODE_NAME and MY_COOKIE
    ip = ip or load_env_var('MY_POD_IP')
    erlang_cookie = load_env_var('ERLANG_COOKIE')
    os.environ['MY_NODE_NAME'] = "%s@%s" % (repo, ip)
    os.environ['MY_COOKIE'] = erlang_cookie
    if is_distillery(customer_app_name):
        set_distillery_env(repo)

    # this is sort of dangerous. the current release
    # might have changed between here and when init
    # was called. (init called when container started. 
    # this called later during remote_console or something)
    # that could cause some confusion..
    # TODO: fetch the right release version from disk.
    # TODO: upgrade should update the release version.
    load_configs(release)

    with cd('/app'):
        exec_fn(logplex_token, customer_app_name, repo, hostname)

def set_distillery_env(repo):
    # TODO: now that we are no longer elixir-only, some of these things should be moved so
    # that they are only done for elixir apps. For example, ERLANG_COOKIE, vm.args stuff
    # REPLACE_OS_VARS, MY_NODE_NAME, libcluster stuff.
    # used only for distillery mode. indicates whether to generate and use default vm.args
    # so that MY_NODE_NAME and MY_COOKIE work out of the box.
    os.environ['GIGALIXIR_DEFAULT_VMARGS'] = "true"
    # mix mode does not replace os vars at runtime.
    os.environ['REPLACE_OS_VARS'] = "true"
    os.environ['RELX_REPLACE_OS_VARS'] = "true"
    # if in mix mode, these are baked in at compile time
    os.environ['LIBCLUSTER_KUBERNETES_SELECTOR'] = "repo=%s" % repo
    os.environ['LIBCLUSTER_KUBERNETES_NODE_BASENAME'] = repo

def maybe_use_default_vm_args():
    if os.environ['GIGALIXIR_DEFAULT_VMARGS'].lower() == "true":
        # bypass all the distillery vm.args stuff and use our own
        # we manually set VMARGS_PATH to say to distillery, use this one
        # not any of the million other possible vm.args
        # this means we have to do variable substitution ourselves though =(
        generate_vmargs(os.environ[ 'MY_NODE_NAME' ], os.environ[ 'MY_COOKIE' ])

        # this needs to be here instead of in the kubernetes spec because
        # we need it for all commands e.g. remote_console, not just init
        # os.environ.set('RELEASE_CONFIG_DIR', "/release-config")
        os.environ['VMARGS_PATH'] = "/release-config/vm.args"

def log_start_and_stop_web(logplex_token, appname, hostname):
    # send some info through the log shuttle really quick to inform the customer
    # that their app is attempting to start.
    # port is None when running remote_console or something like that.
    port = os.environ.get('PORT')
    log(logplex_token, appname, hostname, "Attempting to start '%s' on host '%s'\nAttempting health checks on port %s\n" % (appname, hostname, port))

    # log when shutting down.
    def handle_sigterm(signum, frame):
        log(logplex_token, appname, hostname, "Shutting down '%s' on host '%s'\n" % (appname, hostname))
        sys.exit(0)
    signal.signal(signal.SIGTERM, handle_sigterm)

def pipe_to_log_shuttle(ps, cmd, logplex_token, appname, hostname):
    procid = ' '.join(cmd)
    log_shuttle_cmd = "/opt/gigalixir/bin/log-shuttle -logs-url=http://token:%s@post.logs.gigalixir.com/logs -appname %s -hostname %s -procid %s -num-outlets 1 -batch-size=5 -back-buff=5000" % (logplex_token, appname, hostname, hostname)
    return subprocess.check_call(log_shuttle_cmd.split(), stdin=ps.stdout)


def foreman_start(customer_app_name, cmd):
    # named GIGALIXIR_APP_NAME because it is an env var that gigalixir creates
    # and uses as opposed to a customer provided one. we prefix with GIGALIXIR_
    # to namespace it so they can still set vars called "APP_NAME".. although
    # they can't really? used in Procfile
    os.environ['GIGALIXIR_APP_NAME'] = customer_app_name
    os.environ['GIGALIXIR_COMMAND'] = ' '.join(cmd)
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    # when you use -f, foreman changes the current working dir
    # to the folder the Procfile is in. We set `-d .` to keep
    # it the current dir.
    return subprocess.Popen(['foreman', 'start', '-d', '.', '--color', '--no-timestamp', '-f', procfile_path(os.getcwd())], stdout=subprocess.PIPE)

def distillery_command(customer_app_name, cmd, logplex_token, appname, hostname):
    app_path = '/app/bin/%s' % customer_app_name
    return shell_command([app_path] + list(cmd), logplex_token, appname, hostname)

def distillery_command_exec(customer_app_name, cmd):
    app_path = '/app/bin/%s' % customer_app_name
    # no need to return, this replaces the process
    os.execv(app_path, [app_path] + list(cmd))

def shell_command(cmd, logplex_token, appname, hostname):
    try:
        return subprocess.Popen(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as e:
        log(logplex_token, appname, hostname, str(e))
        raise

def shell_command_exec(cmd, ip, logplex_token, appname, hostname):
    if list(cmd) == ['remote_console']:
        # iex_path = distutils.spawn.find_executable('iex')
        os.execvp('iex', ['iex', '--name', 'remsh@%s' % ip, '--cookie', os.environ['MY_COOKIE'], '--remsh', os.environ['MY_NODE_NAME']])
    else:
        cmd = list(cmd)
        os.execvp(cmd[0], cmd)

def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

def procfile_path(cwd):
    if not os.path.exists("%s/Procfile" % cwd):
        # this is still necessary because the distillery buildpack does not
        # put the Procfile inside the distilery release tarball.
        return '/opt/gigalixir/Procfile'
    else:
        return 'Procfile'

def load_profile():
    # even though /app/.bashrc loads the profile, this
    # still needs to be here for the init case. the init
    # case i.e. docker run ... gigalixir-run init does not
    # start bash so .bashrc is not sourced.
    # ssh into this container runs .bashrc so the user
    # has access to mix and stuff
    # move this into the functions that need it
    # e.g. init, job, distillery_job
    # not upgrade, run, bootstrap
    for f in glob.glob("/app/.profile.d/*.sh"):
        source(f)

# from https://stackoverflow.com/a/7198338/365377
def source(script):
    source = 'source %s' % script
    activate = 'source /tmp/gigalixir/bin/activate'
    deactivate = 'deactivate'
    dump = '/usr/bin/python -c "import os, json;print json.dumps(dict(os.environ))"'
    pipe = subprocess.Popen(['/bin/bash', '-c', '%s && %s && %s && %s' %(source,activate,dump,deactivate)], stdout=subprocess.PIPE)
    env = json.loads(pipe.stdout.read())
    os.environ.update(env)
    return env

def log(logplex_token, appname, hostname, line):
    read, write = os.pipe()
    os.write(write, line)
    os.close(write)

    procid = "gigalixir-run"
    log_shuttle_cmd = "/opt/gigalixir/bin/log-shuttle -logs-url=http://token:%s@post.logs.gigalixir.com/logs -appname %s -hostname %s -procid %s" % (logplex_token, appname, hostname, procid)
    subprocess.check_call(log_shuttle_cmd.split(), stdin=read)

def download_file(url, local_filename):
    # NOTE the stream=True parameter
    r = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                #f.flush() commented by recommendation from J.F.Sebastian
    return local_filename

@contextlib.contextmanager
def cd(newdir, cleanup=lambda: True):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)
        cleanup()

def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)

def start_ssh(repo, app_key):
    # I wanted to put this at /app/.ssh since the root user's home dir is /app
    # but it caused strange behavior. 
    # ssh -t root@localhost -p 32924
    # would work for the first few seconds and then stop working with
    # permission denied (public key) or something
    # it seemed to be a timing issue.. not sure what is going on so I just moved
    # it back to /root/.ssh and all works fine.
    ssh_config = "/root/.ssh"
    if not os.path.exists(ssh_config):
        os.makedirs(ssh_config)

    # I can't bake this into the image because the env vars are not available at build time. We set it up here
    # at container startup.
    update_authorized_keys_cmd = "curl https://api.gigalixir.com/api/apps/%s/ssh_keys -u %s:%s | jq -r '.data | .[]' > /root/.ssh/authorized_keys" % (repo, repo, app_key)

    subprocess.check_call(['/bin/bash', '-c', update_authorized_keys_cmd])

    p = subprocess.Popen(['crontab'], stdin=subprocess.PIPE)
    p.communicate("* * * * * %s && echo $(date) >> /var/log/cron.log\n" % update_authorized_keys_cmd)
    p.stdin.close()

    subprocess.check_call(['cron'])

    # Upstart, systemd, etc do not run in docker containers, nor do I want them to. 
    # We start the ssh server manually on init. This is not an ideal solution, but
    # is a fine place to start. If the SSH server dies it won't respawn, but I think
    # that is okay for now.
    # SSH is needed for observer and remote_console.
    # Cron is needed to update ssh keys>
    subprocess.check_call(['service', 'ssh', 'start'])

def current_release(host, repo, app_key):
    r = requests.get("%s/api/apps/%s/releases/current" % (host, repo), auth = (repo, app_key)) 
    if r.status_code != 200:
        raise Exception(r)
    return r.json()["data"]

def get_hostname():
    return subprocess.check_output(["hostname"]).strip()

def load_env_var(name):
    if name in os.environ:
        return os.environ[name]
    else:
        # These vars are set by the pod spec and are present EXCEPT when you ssh in manually
        # as is the case when you run remote observer or want a remote_console. In those cases
        # we pull them from the file system instead. It's a bit of a hack. The init script
        # creates those files.
        kube_var_path = "/kube-env-vars"
        path = '%s/%s' % (kube_var_path, name)
        if not os.path.exists(path):
            raise Exception("could not find %s in env or in /kube-env-vars" % name)
        else:
            with open(path, 'r') as f:
                value = f.read()
            return value


def is_distillery(customer_app_name):
    app_path = '/app/bin/%s' % customer_app_name
    return is_exe(app_path)
