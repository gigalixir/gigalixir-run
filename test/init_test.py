# This Python file uses the following encoding: utf-8
import os
from sure import expect
import subprocess
import click
from click.testing import CliRunner
import httpretty
import gigalixir_run
import mock
import functools

# test job and distillery_job
FOREMAN_START = [
   mock.call.getcwd(),
   # mock.call.getcwd().__str__(),
   mock.mock._Call(('getcwd().__str__', (), {})),
   # mock.call.path.exists("<MagicMock name='os.getcwd()' id='140584589842768'>/Procfile"),
   mock.call.path.exists(mock.ANY),
   mock.call.path.exists().__nonzero__(),
]
PERSIST_ENV = [
   mock.call.path.exists('/kube-env-vars'),
   mock.call.path.exists().__nonzero__(),
]
EXTRACT_FILE = [
   mock.call.getcwd(),
   mock.call.path.expanduser('/app'),
   # mock.call.chdir(<MagicMock name='os.path.expanduser()' id='140584589731088'>),
   mock.call.chdir(mock.ANY),
   # mock.call.chdir(<MagicMock name='os.getcwd()' id='140584589842768'>),
   mock.call.chdir(mock.ANY),
]
START_EPMD = [
   mock.call.walk('/app'),
   # mock.call.walk().__iter__(),
   mock.mock._Call(('walk().__iter__', (), {})),
]
START_SSH = [
   mock.call.path.exists('/root/.ssh'),
   mock.call.path.exists().__nonzero__(),
]
GENERATE_VMARGS = [
   # mock.call.path.dirname('/home/js/Development/gigalixir-run/gigalixir_run/__init__.pyc'),
   mock.call.path.dirname(mock.ANY),
   mock.call.path.join(mock.ANY, 'templates/vm.args.mustache'),
   mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/REPO',), {})),
   mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/APP_KEY',), {})),
   mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/ERLANG_COOKIE',), {})),
   mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/LOGPLEX_TOKEN',), {})),
   mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/APP',), {})),
   mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/MY_POD_IP',), {})),
]
LOG_MESSAGE = [
   mock.call.pipe(),
   # mock.call.write(<Mock name='pipe_write' id='140584625038544'>, "Attempting to start 'my_app' on host '<MagicMock name='subprocess.check_output().strip()' id='140584587942160'>'\nAttempting health checks on port <MagicMock name='os.environ.get()' id='140584588716240'>\n"),
   mock.call.write(mock.ANY, mock.ANY),
   # mock.call.close(<Mock name='pipe_write' id='140584625038544'>),
   mock.call.close(mock.ANY),
]

IS_DISTILLERY_FALSE = [
    # access is not called when short circuited
    mock.call.path.isfile('/app/bin/fake-customer-app-name'),
]
IS_DISTILLERY_TRUE = [
   mock.call.path.isfile('/app/bin/fake-customer-app-name'),
   # mock.call.path.isfile().__nonzero__(),
   mock.call.access('/app/bin/fake-customer-app-name', os.X_OK),
   mock.call.access().__nonzero__(),
]
EXIT_APP_FOLDER = [
   # mock.call.chdir(<MagicMock name='os.getcwd()' id='140584589842768'>)
   mock.call.chdir(mock.ANY)
]
ENTER_APP_FOLDER = [
   mock.call.getcwd(),
   mock.call.path.expanduser('/app'),
   # mock.call.chdir(<MagicMock name='os.path.expanduser()' id='140584589731088'>),
   mock.call.chdir(mock.ANY),
]

def mocked_open_fn(app_name):
    def mocked_open(*args, **kwargs):
        if args == ("/kube-env-vars/REPO", 'r'):
            return mock.mock_open(read_data=app_name).return_value
        elif args == ("/kube-env-vars/APP_KEY", 'r'):
            return mock.mock_open(read_data="fake-app-key").return_value
        elif args == ("/kube-env-vars/ERLANG_COOKIE", 'r'):
            return mock.mock_open(read_data="fake-cookie").return_value
        elif args == ("/kube-env-vars/LOGPLEX_TOKEN", 'r'):
            return mock.mock_open(read_data="fake-logplex-token").return_value
        elif args == ("/kube-env-vars/APP", 'r'):
            return mock.mock_open(read_data="fake-customer-app-name").return_value
        elif args == ("/kube-env-vars/MY_POD_IP", 'r'):
            return mock.mock_open(read_data="1.2.3.4").return_value
        else:
            return mock.mock_open().return_value
    return mocked_open

def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def iter_content(self, chunk_size):
            # when downloading a file, this is used
            # no content.
            return []

    if args[0] == 'https://api.gigalixir.com/api/apps/my_app/releases/current':
        return MockResponse({"data": {
            "slug_url": "https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz",
            "customer_app_name": "fake-customer-app-name",
            "config": {
                "DATABASE_URL": "fake-database-url",
                "FOO": """1
2"""
            },
            "capabilities": {
                "distillery": {
                    "eval": "erlang"
                }
            },
        }}, 200)
    elif args[0] == 'https://api.gigalixir.com/api/apps/distillery_2/releases/current':
        return MockResponse({"data": {
            "slug_url": "https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz",
            "customer_app_name": "fake-customer-app-name",
            "config": {
                "DATABASE_URL": "fake-database-url",
                "FOO": """1
2"""
            },
            "capabilities": {
                "distillery": {
                    "eval": "elixir"
                }
            },
        }}, 200)
    elif args[0] == 'https://api.gigalixir.com/api/apps/my_custom_vmargs_app/releases/current':
        return MockResponse({"data": {
            "slug_url": "https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz",
            "customer_app_name": "fake-customer-app-name",
            "config": {
                "DATABASE_URL": "fake-database-url",
                "GIGALIXIR_DEFAULT_VMARGS": "false"
            }
        }}, 200)
    elif args[0] == 'https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz':
        return MockResponse(None, 200)
    elif args[0] == 'https://api.gigalixir.com/api/apps/my_app/host_indexes/host1/assign':
        return MockResponse({"data": {
            "index": 1
        }}, 200)
    elif args[0] == 'https://api.gigalixir.com/api/apps/my_custom_vmargs_app/host_indexes/host1/assign':
        return MockResponse({"data": {
            "index": 1
        }}, 200)

    return MockResponse(None, 404)

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_mix_init(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = False
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        os.environ['APP_KEY'] = 'fake-app-key'
        my_env['PORT'] = '4000'
        
        # set once for Click and once for gigalixir_run
        os.environ['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        os.environ['ERLANG_COOKIE'] = 'fake-cookie'
        os.environ['MY_POD_IP'] = '1.2.3.4'
        my_env['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        my_env['ERLANG_COOKIE'] = 'fake-cookie'
        my_env['MY_POD_IP'] = '1.2.3.4'
        my_env['HOSTNAME'] = 'host1'

        result = runner.invoke(gigalixir_run.cli, ['init', 'my_app', 'foreground'])
        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'GIGALIXIR_APP_NAME': 'fake-customer-app-name', 
            'GIGALIXIR_COMMAND': u'foreground', 
            'PYTHONIOENCODING': 'utf-8', 
            'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            'PORT': '4000', 
            'LOGPLEX_TOKEN': 'fake-logplex-token', 
            'HOSTNAME': 'host1',
            'HOST_INDEX': '1'
        }

        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
        ] + START_SSH + [
        ] + PERSIST_ENV + [
        ] + EXTRACT_FILE + [
        ] + START_EPMD + [
        ] + IS_DISTILLERY_FALSE + [
        ] + ENTER_APP_FOLDER + [
        ] + LOG_MESSAGE + [
        ] + IS_DISTILLERY_FALSE + [
        ] + FOREMAN_START + [
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
            mock.call.check_call(['/bin/bash', '-c', u"curl https://api.gigalixir.com/api/apps/my_app/ssh_keys -u my_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys"]),
            mock.call.Popen(['crontab'], stdin=stdin),
            mock.call.Popen().communicate(u"* * * * * curl https://api.gigalixir.com/api/apps/my_app/ssh_keys -u my_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys && echo $(date) >> /var/log/cron.log\n"),
            mock.call.Popen().stdin.close(),
            mock.call.check_call(['cron']),
            mock.call.check_call(['service', 'ssh', 'start']),
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            mock.call.Popen(['foreman', 'start', '-d', '.', '--color', '--no-timestamp', '-f', 'Procfile'], stdout=stdin),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            # -hostname and -procid have 3 mock.ANYs behind it because
            # the string representation of MagicMock is broken into
            # 3 strings.. ugly.
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/host_indexes/host1/assign', auth=(u'my_app', u'fake-app-key'), headers={'Content-Type': 'application/json'}),
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
            mock.call('https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz', stream=True),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/MY_POD_IP', 'w'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'w'),
            mock.call('/kube-env-vars/REPO', 'w'),
            mock.call('/kube-env-vars/APP', 'w'),
            mock.call('/kube-env-vars/APP_KEY', 'w'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'w'),
            mock.call('/app/fake-customer-app-name.tar.gz', 'wb'),

            # no vmargs generated for mix
            # generate_vmargs
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            # mock.call(mock.ANY, 'r'),
            # mock.call('/release-config/vm.args', 'w'),
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_distillery_init(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = True
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        os.environ['APP_KEY'] = 'fake-app-key'
        my_env['PORT'] = '4000'
        
        # set once for Click and once for gigalixir_run
        os.environ['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        os.environ['ERLANG_COOKIE'] = 'fake-cookie'
        os.environ['MY_POD_IP'] = '1.2.3.4'
        my_env['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        my_env['ERLANG_COOKIE'] = 'fake-cookie'
        my_env['MY_POD_IP'] = '1.2.3.4'
        my_env['HOSTNAME'] = 'host1'

        result = runner.invoke(gigalixir_run.cli, ['init', 'my_app', 'foreground'])
        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'GIGALIXIR_APP_NAME': 'fake-customer-app-name', 
            'GIGALIXIR_COMMAND': u'foreground', 
            'PYTHONIOENCODING': 'utf-8', 
            'GIGALIXIR_DEFAULT_VMARGS': 'true', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'my_app', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=my_app', 
            'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            'PORT': '4000', 
            'LOGPLEX_TOKEN': 'fake-logplex-token', 
            'VMARGS_PATH': '/release-config/vm.args',
            'HOSTNAME': 'host1',
            'HOST_INDEX': '1'
        }

        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
        ] + START_SSH + [
        ] + PERSIST_ENV + [
        ] + EXTRACT_FILE + [
        ] + START_EPMD + [
        ] + IS_DISTILLERY_TRUE + [
        ] + ENTER_APP_FOLDER + [
        ] + LOG_MESSAGE + [
        ] + IS_DISTILLERY_TRUE + [
        ] + GENERATE_VMARGS + [
        ] + FOREMAN_START + [
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
            mock.call.check_call(['/bin/bash', '-c', u"curl https://api.gigalixir.com/api/apps/my_app/ssh_keys -u my_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys"]),
            mock.call.Popen(['crontab'], stdin=stdin),
            mock.call.Popen().communicate(u"* * * * * curl https://api.gigalixir.com/api/apps/my_app/ssh_keys -u my_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys && echo $(date) >> /var/log/cron.log\n"),
            mock.call.Popen().stdin.close(),
            mock.call.check_call(['cron']),
            mock.call.check_call(['service', 'ssh', 'start']),
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            mock.call.Popen(['foreman', 'start', '-d', '.', '--color', '--no-timestamp', '-f', 'Procfile'], stdout=stdin),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            # -hostname and -procid have 3 mock.ANYs behind it because
            # the string representation of MagicMock is broken into
            # 3 strings.. ugly.
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/host_indexes/host1/assign', auth=(u'my_app', u'fake-app-key'), headers={'Content-Type': 'application/json'}),
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
            mock.call('https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz', stream=True),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/MY_POD_IP', 'w'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'w'),
            mock.call('/kube-env-vars/REPO', 'w'),
            mock.call('/kube-env-vars/APP', 'w'),
            mock.call('/kube-env-vars/APP_KEY', 'w'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'w'),
            mock.call('/app/fake-customer-app-name.tar.gz', 'wb'),

            # generate_vmargs
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            mock.call(mock.ANY, 'r'),
            mock.call('/release-config/vm.args', 'w'),
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_custom_vmargs_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_custom_vmargs_init(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = True
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        os.environ['APP_KEY'] = 'fake-app-key'
        my_env['PORT'] = '4000'
        
        # set once for Click and once for gigalixir_run
        os.environ['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        os.environ['ERLANG_COOKIE'] = 'fake-cookie'
        os.environ['MY_POD_IP'] = '1.2.3.4'
        my_env['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        my_env['ERLANG_COOKIE'] = 'fake-cookie'
        my_env['MY_POD_IP'] = '1.2.3.4'
        my_env['HOSTNAME'] = 'host1'

        result = runner.invoke(gigalixir_run.cli, ['init', 'my_custom_vmargs_app', 'foreground'])
        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'my_custom_vmargs_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'GIGALIXIR_APP_NAME': 'fake-customer-app-name', 
            'GIGALIXIR_COMMAND': u'foreground', 
            'PYTHONIOENCODING': 'utf-8', 
            'GIGALIXIR_DEFAULT_VMARGS': 'false', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'my_custom_vmargs_app', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=my_custom_vmargs_app', 
            'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_custom_vmargs_app@1.2.3.4', 
            'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'PORT': '4000', 
            'LOGPLEX_TOKEN': 'fake-logplex-token', 
            # no VMARGS_PATH for custom vmargs
            # 'VMARGS_PATH': '/release-config/vm.args'
            'HOSTNAME': 'host1',
            'HOST_INDEX': '1'
        }

        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
        ] + START_SSH + [
        ] + PERSIST_ENV + [
        ] + EXTRACT_FILE + [
        ] + START_EPMD + [
        ] + IS_DISTILLERY_TRUE + [
        ] + ENTER_APP_FOLDER + [
        ] + LOG_MESSAGE + [
        ] + IS_DISTILLERY_TRUE + [
        # not for custom_vmargs
        # ] + GENERATE_VMARGS + [
        ] + FOREMAN_START + [
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
            mock.call.check_call(['/bin/bash', '-c', u"curl https://api.gigalixir.com/api/apps/my_custom_vmargs_app/ssh_keys -u my_custom_vmargs_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys"]),
            mock.call.Popen(['crontab'], stdin=stdin),
            mock.call.Popen().communicate(u"* * * * * curl https://api.gigalixir.com/api/apps/my_custom_vmargs_app/ssh_keys -u my_custom_vmargs_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys && echo $(date) >> /var/log/cron.log\n"),
            mock.call.Popen().stdin.close(),
            mock.call.check_call(['cron']),
            mock.call.check_call(['service', 'ssh', 'start']),
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_custom_vmargs_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            mock.call.Popen(['foreman', 'start', '-d', '.', '--color', '--no-timestamp', '-f', 'Procfile'], stdout=stdin),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            mock.mock._Call(('check_output().strip().__unicode__', (), {})),
            # -hostname and -procid have 3 mock.ANYs behind it because
            # the string representation of MagicMock is broken into
            # 3 strings.. ugly.
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_custom_vmargs_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_custom_vmargs_app/host_indexes/host1/assign', auth=(u'my_custom_vmargs_app', u'fake-app-key'), headers={'Content-Type': 'application/json'}),
            mock.call(u'https://api.gigalixir.com/api/apps/my_custom_vmargs_app/releases/current', auth=(u'my_custom_vmargs_app', u'fake-app-key')),
            mock.call('https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz', stream=True),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/MY_POD_IP', 'w'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'w'),
            mock.call('/kube-env-vars/REPO', 'w'),
            mock.call('/kube-env-vars/APP', 'w'),
            mock.call('/kube-env-vars/APP_KEY', 'w'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'w'),
            mock.call('/app/fake-customer-app-name.tar.gz', 'wb'),
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_run_mix_remote_console(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = False
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'

        result = runner.invoke(gigalixir_run.cli, ['run', 'remote_console'])

        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            # 'PYTHONIOENCODING': 'utf-8', 
            # 'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            # 'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            # 'PORT': '4000', 
            # 'LOGPLEX_TOKEN': '', 
        }

        assert mock_tarfile.mock_calls == [
        ]

        assert mock_os.mock_calls == [
            # load_env_var REPO
            mock.call.path.exists('/kube-env-vars/REPO'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/APP_KEY'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/MY_POD_IP'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/LOGPLEX_TOKEN'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/ERLANG_COOKIE'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_FALSE + [
        ] + ENTER_APP_FOLDER + [
        ] + IS_DISTILLERY_FALSE + [
            # call.execv('/home/js/.asdf/shims/iex', ['/home/js/.asdf/shims/iex', '--name', 'remsh@1.2.3.4', '--cookie', '', '--remsh', 'my_app@1.2.3.4']) 
            mock.call.execvp('iex', ['iex', '--name', 'remsh@1.2.3.4', '--cookie', 'fake-cookie', '--remsh', 'my_app@1.2.3.4']),
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
           mock.call.check_output(['hostname']),
           mock.call.check_output().strip(),
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),
            # generate_vmargs not needed for mix mode
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            # mock.call(mock.ANY, 'r'),
            # mock.call('/release-config/vm.args', 'w')
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_run_distillery_remote_console(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = True
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'

        result = runner.invoke(gigalixir_run.cli, ['run', 'remote_console'])

        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'GIGALIXIR_DEFAULT_VMARGS': 'true', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'my_app', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=my_app', 
            # 'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            # 'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            # 'PORT': '4000', 
            # 'LOGPLEX_TOKEN': '', 
            'VMARGS_PATH': '/release-config/vm.args'
        }

        assert mock_tarfile.mock_calls == [
        ]

        assert mock_os.mock_calls == [
            # load_env_var REPO
            mock.call.path.exists('/kube-env-vars/REPO'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/APP_KEY'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/MY_POD_IP'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/LOGPLEX_TOKEN'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/ERLANG_COOKIE'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_TRUE + [
        ] + ENTER_APP_FOLDER + [
        ] + IS_DISTILLERY_TRUE + [
        ] + GENERATE_VMARGS + [
            mock.call.execv('/app/bin/fake-customer-app-name', ['/app/bin/fake-customer-app-name', 'remote_console']),
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
           mock.call.check_output(['hostname']),
           mock.call.check_output().strip(),
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),
            # generate_vmargs not needed for remote_console
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            mock.call(mock.ANY, 'r'),
            mock.call('/release-config/vm.args', 'w')
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_upgrade(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = True
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'

        result = runner.invoke(gigalixir_run.cli, ['upgrade', '0.0.2'])

        assert result.output == ''
        assert result.exit_code == 0
        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
            # load_env_var REPO
            mock.call.path.exists('/kube-env-vars/APP'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/REPO'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/APP_KEY'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_TRUE + [
            mock.call.path.exists('/app/releases/0.0.2'),
            mock.call.path.exists().__nonzero__(),
            # enter release folder
            mock.call.getcwd(),
            mock.call.path.expanduser('/app/releases/0.0.2'),
            # call.chdir(<MagicMock name='os.path.expanduser()' id='140244186656208'>)
            mock.call.chdir(mock.ANY),
            # exit release folder
            # call.chdir(<MagicMock name='os.getcwd()' id='140539945091920'>)
            mock.call.chdir(mock.ANY),

            mock.call.path.exists('/kube-env-vars/LOGPLEX_TOKEN'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/MY_POD_IP'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/ERLANG_COOKIE'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_TRUE + [
        ] + ENTER_APP_FOLDER + [
        ] + LOG_MESSAGE + [
        ] + GENERATE_VMARGS + [
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            mock.call.Popen(['/app/bin/fake-customer-app-name', 'upgrade', '0.0.2'], stderr=mock.ANY, stdout=stdin),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
            mock.call(u'https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz', stream=True),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/APP', 'r'),
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/app/releases/0.0.2/fake-customer-app-name.tar.gz', 'wb'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),

            # generate_vmargs
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            mock.call(mock.ANY, 'r'),
            mock.call('/release-config/vm.args', 'w'),
        ]

        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'GIGALIXIR_DEFAULT_VMARGS': 'true', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'my_app', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=my_app', 
            # 'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            # 'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            # 'PORT': '4000', 
            # 'LOGPLEX_TOKEN': '', 
            'VMARGS_PATH': '/release-config/vm.args'
        }

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_run_mix_shell_with_no_cmd(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = False
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'

        result = runner.invoke(gigalixir_run.cli, ['shell', '--'])

        assert "Missing argument \"cmd\"" in result.output
        assert result.exit_code == 2
        assert mock_tarfile.mock_calls == [
        ]

        assert mock_os.mock_calls == [
        ]

        assert mock_subprocess.mock_calls == [
        ]

        assert mock_get.mock_calls == [
        ]

        assert mock_open.mock_calls == [
        ]

        assert my_env == {
        }

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_run_mix_shell(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = False
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'

        result = runner.invoke(gigalixir_run.cli, ['run', 'mix', 'ecto.migrate'])

        assert result.output == ''
        assert result.exit_code == 0
        assert mock_tarfile.mock_calls == [
        ]

        assert mock_os.mock_calls == [
            # load_env_var REPO
            mock.call.path.exists('/kube-env-vars/REPO'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/APP_KEY'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/MY_POD_IP'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/LOGPLEX_TOKEN'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/ERLANG_COOKIE'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_FALSE + [
        ] + ENTER_APP_FOLDER + [
        ] + IS_DISTILLERY_FALSE + [
            mock.call.execvp('mix', ['mix', 'ecto.migrate']),
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),
        ]

        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            # 'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            # 'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            # 'PORT': '4000', 
        }

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_mix_job(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = False
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        my_env['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        my_env['ERLANG_COOKIE'] = 'fake-cookie'
        my_env['MY_POD_IP'] = '1.2.3.4'
        my_env['REPO'] = 'my_app'
        my_env['APP_KEY'] = 'fake-app-key'

        result = runner.invoke(gigalixir_run.cli, ['job', 'mix', 'ecto.migrate'])
        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'REPO': 'my_app',
            'APP_KEY': 'fake-app-key',
            'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            'LOGPLEX_TOKEN': 'fake-logplex-token', 
        }

        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
        ] + EXTRACT_FILE + [
        ] + IS_DISTILLERY_FALSE + [
        ] + ENTER_APP_FOLDER + [
        ] + LOG_MESSAGE + [
        ] + IS_DISTILLERY_FALSE + [
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            mock.call.Popen(['mix', 'ecto.migrate'], stderr=mock.ANY, stdout=stdin),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # -hostname and -procid have 3 mock.ANYs behind it because
            # the string representation of MagicMock is broken into
            # 3 strings.. ugly.
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
            mock.call('https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz', stream=True),
        ]

        assert mock_open.mock_calls == [
            mock.call('/app/fake-customer-app-name.tar.gz', 'wb'),
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_distillery_job(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = True
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        my_env['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        my_env['ERLANG_COOKIE'] = 'fake-cookie'
        my_env['MY_POD_IP'] = '1.2.3.4'
        my_env['REPO'] = 'my_app'
        my_env['APP_KEY'] = 'fake-app-key'

        result = runner.invoke(gigalixir_run.cli, ['distillery_job', 'command', 'Elixir.Task', 'migrate'])
        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'VMARGS_PATH': '/release-config/vm.args',
            'GIGALIXIR_DEFAULT_VMARGS': 'true', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'my_app', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=my_app', 
            'REPO': 'my_app',
            'APP_KEY': 'fake-app-key',
            'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            'LOGPLEX_TOKEN': 'fake-logplex-token', 
        }

        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
        ] + EXTRACT_FILE + [
        ] + IS_DISTILLERY_TRUE + [
        ] + IS_DISTILLERY_TRUE + [
        ] + ENTER_APP_FOLDER + [
        ] + LOG_MESSAGE + [
        ] + GENERATE_VMARGS + [
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            mock.call.Popen(['/app/bin/fake-customer-app-name', 'command', 'Elixir.Task', 'migrate'], stderr=mock.ANY, stdout=stdin),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # -hostname and -procid have 3 mock.ANYs behind it because
            # the string representation of MagicMock is broken into
            # 3 strings.. ugly.
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:fake-logplex-token@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
            mock.call('https://storage.googleapis.com/slug-bucket/production/sunny-wellgroomed-africanpiedkingfisher/releases/0.0.2/SHA/gigalixir_getting_started.tar.gz', stream=True),
        ]

        assert mock_open.mock_calls == [
            mock.call('/app/fake-customer-app-name.tar.gz', 'wb'),
            # generate_vmargs
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            mock.call(mock.ANY, 'r'),
            mock.call('/release-config/vm.args', 'w'),
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_distillery_eval(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = True
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'

        result = runner.invoke(gigalixir_run.cli, ['distillery_eval', 'node().'])

        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'my_app@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'GIGALIXIR_DEFAULT_VMARGS': 'true', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'my_app', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=my_app', 
            # 'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            # 'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            # 'PORT': '4000', 
            # 'LOGPLEX_TOKEN': '', 
            'VMARGS_PATH': '/release-config/vm.args'
        }

        assert mock_tarfile.mock_calls == [
        ]

        assert mock_os.mock_calls == [
            # load_env_var REPO
            mock.call.path.exists('/kube-env-vars/APP'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_TRUE + [
            mock.call.path.exists('/kube-env-vars/REPO'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/APP_KEY'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/MY_POD_IP'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/LOGPLEX_TOKEN'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/ERLANG_COOKIE'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_TRUE + [
        ] + ENTER_APP_FOLDER + [
        ] + GENERATE_VMARGS + [
            mock.call.execv('/app/bin/fake-customer-app-name', ['/app/bin/fake-customer-app-name', 'eval', 'node().']),
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
           mock.call.check_output(['hostname']),
           mock.call.check_output().strip(),
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/APP', 'r'),
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),
            # generate_vmargs not needed for remote_console
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            mock.call(mock.ANY, 'r'),
            mock.call('/release-config/vm.args', 'w')
        ]

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("distillery_2"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_distillery_2_eval(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    mock_os.path.isfile.return_value = True
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env
    mock_os.X_OK = os.X_OK

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'

        result = runner.invoke(gigalixir_run.cli, ['distillery_eval', 'IO.inspect 123'])

        assert result.output == ''
        assert result.exit_code == 0
        assert my_env == {
            'RELEASE_NODE': 'distillery_2@1.2.3.4',
            'RELEASE_DISTRIBUTION': 'name',
            'GIGALIXIR_DEFAULT_VMARGS': 'true', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'distillery_2', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=distillery_2', 
            # 'MY_POD_IP': '1.2.3.4', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': 'fake-cookie', 
            'MY_NODE_NAME': 'distillery_2@1.2.3.4', 
            # 'ERLANG_COOKIE': 'fake-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            # 'PORT': '4000', 
            # 'LOGPLEX_TOKEN': '', 
            'VMARGS_PATH': '/release-config/vm.args'
        }

        assert mock_tarfile.mock_calls == [
        ]

        assert mock_os.mock_calls == [
            # load_env_var REPO
            mock.call.path.exists('/kube-env-vars/APP'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_TRUE + [
            mock.call.path.exists('/kube-env-vars/REPO'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/APP_KEY'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/MY_POD_IP'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/LOGPLEX_TOKEN'),
            mock.call.path.exists().__nonzero__(),
            mock.call.path.exists('/kube-env-vars/ERLANG_COOKIE'),
            mock.call.path.exists().__nonzero__(),
        ] + IS_DISTILLERY_TRUE + [
        ] + ENTER_APP_FOLDER + [
        ] + GENERATE_VMARGS + [
            mock.call.execv('/app/bin/fake-customer-app-name', ['/app/bin/fake-customer-app-name', 'rpc', 'IO.inspect 123']),
        ] + EXIT_APP_FOLDER + [
        ]

        assert mock_subprocess.mock_calls == [
           mock.call.check_output(['hostname']),
           mock.call.check_output().strip(),
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/distillery_2/releases/current', auth=(u'distillery_2', u'fake-app-key')),
            mock.call(u'https://api.gigalixir.com/api/apps/distillery_2/releases/current', auth=(u'distillery_2', u'fake-app-key')),
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/APP', 'r'),
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),
            # generate_vmargs not needed for remote_console
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            mock.call(mock.ANY, 'r'),
            mock.call('/release-config/vm.args', 'w')
        ]
