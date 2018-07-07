# This Python file uses the following encoding: utf-8
import os
from sure import expect
import subprocess
import click
from click.testing import CliRunner
import httpretty
import gigalixir_run
import mock

def mocked_open_fn(app_name):
    def mocked_open(*args, **kwargs):
        if args == ("/kube-env-vars/REPO", 'r'):
            return mock.mock_open(read_data=app_name).return_value
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
            "slug_url": "fake-slug-url",
            "customer_app_name": "fake-customer-app-name",
            "config": {
                "DATABASE_URL": "fake-database-url",
                "FOO": """1
2"""
            }
        }}, 200)
    elif args[0] == 'https://api.gigalixir.com/api/apps/my_custom_vmargs_app/releases/current':
        return MockResponse({"data": {
            "slug_url": "fake-slug-url",
            "customer_app_name": "fake-customer-app-name",
            "config": {
                "DATABASE_URL": "fake-database-url",
                "GIGALIXIR_DEFAULT_VMARGS": "false"
            }
        }}, 200)
    elif args[0] == 'fake-slug-url':
        return MockResponse(None, 200)

    return MockResponse(None, 404)

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_init(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        os.environ['APP_KEY'] = 'fake-app-key'
        my_env['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        my_env['ERLANG_COOKIE'] = 'fake-erlang-cookie'
        my_env['MY_POD_IP'] = '1.2.3.4'
        my_env['PORT'] = '4000'

        result = runner.invoke(gigalixir_run.cli, ['init', 'my_app', 'foreground'])
        assert result.output == ''
        assert result.exit_code == 0
        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
           mock.call.path.exists('/root/.ssh'),
           mock.call.path.exists().__nonzero__(),
           mock.call.path.exists('/kube-env-vars'),
           mock.call.path.exists().__nonzero__(),
           mock.call.getcwd(),
           mock.call.path.expanduser('/app'),
           # mock.call.chdir(<MagicMock name='os.path.expanduser()' id='140584589731088'>),
           mock.call.chdir(mock.ANY),
           # mock.call.chdir(<MagicMock name='os.getcwd()' id='140584589842768'>),
           mock.call.chdir(mock.ANY),
           mock.call.walk('/app'),
           # mock.call.walk().__iter__(),
           mock.mock._Call(('walk().__iter__', (), {})),
           # mock.call.path.dirname('/home/js/Development/gigalixir-run/gigalixir_run/__init__.pyc'),
           mock.call.path.dirname(mock.ANY),
           mock.call.path.join(mock.ANY, 'templates/vm.args.mustache'),
           mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/REPO',), {})),
           mock.mock._Call(('path.join().__eq__', ('/kube-env-vars/MY_POD_IP',), {})),
           mock.call.getcwd(),
           mock.call.path.expanduser('/app'),
           # mock.call.chdir(<MagicMock name='os.path.expanduser()' id='140584589731088'>),
           mock.call.chdir(mock.ANY),
           mock.call.getcwd(),
           # mock.call.getcwd().__str__(),
           mock.mock._Call(('getcwd().__str__', (), {})),
           mock.call.pipe(),
           # mock.call.write(<Mock name='pipe_write' id='140584625038544'>, "Attempting to start 'my_app' on host '<MagicMock name='subprocess.check_output().strip()' id='140584587942160'>'\nAttempting health checks on port <MagicMock name='os.environ.get()' id='140584588716240'>\n"),
           mock.call.write(mock.ANY, mock.ANY),
           # mock.call.close(<Mock name='pipe_write' id='140584625038544'>),
           mock.call.close(mock.ANY),
           mock.call.getcwd(),
           # mock.call.getcwd().__str__(),
           mock.mock._Call(('getcwd().__str__', (), {})),
           # mock.call.path.exists("<MagicMock name='os.getcwd()' id='140584589842768'>/Procfile"),
           mock.call.path.exists(mock.ANY),
           mock.call.path.exists().__nonzero__(),
           # mock.call.chdir(<MagicMock name='os.getcwd()' id='140584589842768'>)
           mock.call.chdir(mock.ANY)
        ]

        print mock_subprocess.mock_calls
        assert mock_subprocess.mock_calls == [
            mock.call.check_call(['/bin/bash', '-c', u"curl https://api.gigalixir.com/api/apps/my_app/ssh_keys -u my_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys"]),
            mock.call.Popen(['crontab'], stdin=stdin),
            mock.call.Popen().communicate(u"* * * * * curl https://api.gigalixir.com/api/apps/my_app/ssh_keys -u my_app:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys && echo $(date) >> /var/log/cron.log\n"),
            mock.call.Popen().stdin.close(),
            mock.call.check_call(['cron']),
            mock.call.check_call(['service', 'ssh', 'start']),
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', '<MagicMock', "name='subprocess.check_output().strip()'", "id='139706507347280'>", '-procid', 'gigalixir-run'], stdin=<Mock name='pipe_read' id='139706509973264'>),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.call.Popen(['foreman', 'start', '-d', '.', '--color', '--no-timestamp', '-f', 'Procfile'], stdout=stdin),
            # mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', '<MagicMock', "name='subprocess.check_output().strip()'", "id='140316095358288'>", '-procid', '<MagicMock', "name='subprocess.check_output().strip()'", "id='140316095358288'>", '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=<MagicMock name='subprocess.Popen().stdout' id='140316095582800'>),
            # -hostname and -procid have 3 mock.ANYs behind it because
            # the string representation of MagicMock is broken into
            # 3 strings.. ugly.
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/my_app/releases/current', auth=(u'my_app', u'fake-app-key')),
            mock.call('fake-slug-url', stream=True),
            mock.call('https://api.gigalixir.com/api/apps/my_app/releases/current', auth=('my_app', ''))
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/MY_POD_IP', 'w'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'w'),
            mock.call('/kube-env-vars/REPO', 'w'),
            mock.call('/kube-env-vars/APP', 'w'),
            mock.call('/kube-env-vars/APP_KEY', 'w'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'w'),
            mock.call('/app/fake-customer-app-name.tar.gz', 'wb'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/kube-env-vars/APP', 'r'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
            # mock.call(<MagicMock name='os.path.join()' id='139897244298064'>, 'r'),
            mock.call(mock.ANY, 'r'),
            mock.call('/release-config/vm.args', 'w')
        ]

        assert my_env == {
            'PYTHONIOENCODING': 'utf-8', 
            'GIGALIXIR_DEFAULT_VMARGS': 'true', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': 'my_app', 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=my_app', 
            'MY_POD_IP': '1.2.3.4', 
            'GIGALIXIR_COMMAND': u'foreground', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': '', 
            'MY_NODE_NAME': 'my_app@1.2.3.4', 
            'GIGALIXIR_APP_NAME': '', 
            'ERLANG_COOKIE': 'fake-erlang-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            'PORT': '4000', 
            'LOGPLEX_TOKEN': '', 
            'VMARGS_PATH': '/release-config/vm.args'
        }

@mock.patch('gigalixir_run.open', side_effect=mocked_open_fn("my_custom_vmargs_app"))
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_custom_vmargs(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    repo = "my_custom_vmargs_app"
    stdin = mock.Mock(name='stdin')
    mock_subprocess.PIPE = stdin

    pipe_read = mock.Mock(name='pipe_read')
    pipe_write = mock.Mock(name='pipe_write')
    mock_os.pipe.return_value = (pipe_read, pipe_write)

    # use a real dictionary for environ
    my_env = dict()
    mock_os.environ = my_env

    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        os.environ['APP_KEY'] = 'fake-app-key'
        my_env['LOGPLEX_TOKEN'] = 'fake-logplex-token'
        my_env['ERLANG_COOKIE'] = 'fake-erlang-cookie'
        my_env['MY_POD_IP'] = '1.2.3.4'
        my_env['PORT'] = '4000'

        result = runner.invoke(gigalixir_run.cli, ['init', repo, 'foreground'])
        assert result.output == ''
        assert result.exit_code == 0
        assert mock_tarfile.mock_calls == [
            mock.call('fake-customer-app-name.tar.gz', 'r:gz'),
            mock.call().extractall(),
            mock.call().close()
        ]

        assert mock_os.mock_calls == [
           mock.call.path.exists('/root/.ssh'),
           mock.call.path.exists().__nonzero__(),
           mock.call.path.exists('/kube-env-vars'),
           mock.call.path.exists().__nonzero__(),
           mock.call.getcwd(),
           mock.call.path.expanduser('/app'),
           # mock.call.chdir(<MagicMock name='os.path.expanduser()' id='140584589731088'>),
           mock.call.chdir(mock.ANY),
           # mock.call.chdir(<MagicMock name='os.getcwd()' id='140584589842768'>),
           mock.call.chdir(mock.ANY),
           mock.call.walk('/app'),
           # mock.call.walk().__iter__(),
           mock.mock._Call(('walk().__iter__', (), {})),
           mock.call.getcwd(),
           mock.call.path.expanduser('/app'),
           # mock.call.chdir(<MagicMock name='os.path.expanduser()' id='140584589731088'>),
           mock.call.chdir(mock.ANY),
           mock.call.getcwd(),
           # mock.call.getcwd().__str__(),
           mock.mock._Call(('getcwd().__str__', (), {})),
           mock.call.pipe(),
           # mock.call.write(<Mock name='pipe_write' id='140584625038544'>, "Attempting to start 'my_app' on host '<MagicMock name='subprocess.check_output().strip()' id='140584587942160'>'\nAttempting health checks on port <MagicMock name='os.environ.get()' id='140584588716240'>\n"),
           mock.call.write(mock.ANY, mock.ANY),
           # mock.call.close(<Mock name='pipe_write' id='140584625038544'>),
           mock.call.close(mock.ANY),
           mock.call.getcwd(),
           # mock.call.getcwd().__str__(),
           mock.mock._Call(('getcwd().__str__', (), {})),
           # mock.call.path.exists("<MagicMock name='os.getcwd()' id='140584589842768'>/Procfile"),
           mock.call.path.exists(mock.ANY),
           mock.call.path.exists().__nonzero__(),
           # mock.call.chdir(<MagicMock name='os.getcwd()' id='140584589842768'>)
           mock.call.chdir(mock.ANY)
        ]

        print mock_subprocess.mock_calls
        assert mock_subprocess.mock_calls == [
            mock.call.check_call(['/bin/bash', '-c', u"curl https://api.gigalixir.com/api/apps/%s/ssh_keys -u %s:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys" % (repo, repo)]),
            mock.call.Popen(['crontab'], stdin=stdin),
            mock.call.Popen().communicate(u"* * * * * curl https://api.gigalixir.com/api/apps/%s/ssh_keys -u %s:fake-app-key | jq -r '.data | .[]' > /root/.ssh/authorized_keys && echo $(date) >> /var/log/cron.log\n" % (repo, repo)),
            mock.call.Popen().stdin.close(),
            mock.call.check_call(['cron']),
            mock.call.check_call(['service', 'ssh', 'start']),
            mock.call.check_output(['hostname']),
            mock.call.check_output().strip(),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', '<MagicMock', "name='subprocess.check_output().strip()'", "id='139706507347280'>", '-procid', 'gigalixir-run'], stdin=<Mock name='pipe_read' id='139706509973264'>),
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', repo, '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', 'gigalixir-run'], stdin=pipe_read),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            # mock.call.check_output().strip().__str__(),
            mock.mock._Call(('check_output().strip().__str__', (), {})),
            mock.call.Popen(['foreman', 'start', '-d', '.', '--color', '--no-timestamp', '-f', 'Procfile'], stdout=stdin),
            # mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', 'my_app', '-hostname', '<MagicMock', "name='subprocess.check_output().strip()'", "id='140316095358288'>", '-procid', '<MagicMock', "name='subprocess.check_output().strip()'", "id='140316095358288'>", '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=<MagicMock name='subprocess.Popen().stdout' id='140316095582800'>),
            # -hostname and -procid have 3 mock.ANYs behind it because
            # the string representation of MagicMock is broken into
            # 3 strings.. ugly.
            mock.call.check_call(['/opt/gigalixir/bin/log-shuttle', '-logs-url=http://token:@post.logs.gigalixir.com/logs', '-appname', repo, '-hostname', mock.ANY, mock.ANY, mock.ANY, '-procid', mock.ANY, mock.ANY, mock.ANY, '-num-outlets', '1', '-batch-size=5', '-back-buff=5000'], stdin=mock.ANY),
            mock.call.Popen().wait()
        ]

        assert mock_get.mock_calls == [
            mock.call(u'https://api.gigalixir.com/api/apps/%s/releases/current' % repo, auth=(repo, u'fake-app-key')),
            mock.call('fake-slug-url', stream=True),
            mock.call('https://api.gigalixir.com/api/apps/%s/releases/current' % repo, auth=(repo, ''))
        ]

        assert mock_open.mock_calls == [
            mock.call('/kube-env-vars/MY_POD_IP', 'w'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'w'),
            mock.call('/kube-env-vars/REPO', 'w'),
            mock.call('/kube-env-vars/APP', 'w'),
            mock.call('/kube-env-vars/APP_KEY', 'w'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'w'),
            mock.call('/app/fake-customer-app-name.tar.gz', 'wb'),
            mock.call('/kube-env-vars/MY_POD_IP', 'r'),
            mock.call('/kube-env-vars/ERLANG_COOKIE', 'r'),
            mock.call('/kube-env-vars/REPO', 'r'),
            mock.call('/kube-env-vars/APP_KEY', 'r'),
            mock.call('/kube-env-vars/APP', 'r'),
            mock.call('/kube-env-vars/LOGPLEX_TOKEN', 'r'),
        ]

        assert my_env == {
            'PYTHONIOENCODING': 'utf-8', 
            'GIGALIXIR_DEFAULT_VMARGS': 'false', 
            'REPLACE_OS_VARS': 'true', 
            'RELX_REPLACE_OS_VARS': 'true', 
            'LIBCLUSTER_KUBERNETES_NODE_BASENAME': repo, 
            'LIBCLUSTER_KUBERNETES_SELECTOR': 'repo=%s' % repo, 
            'MY_POD_IP': '1.2.3.4', 
            'GIGALIXIR_COMMAND': u'foreground', 
            'DATABASE_URL': 'fake-database-url', 
            'MY_COOKIE': '', 
            'MY_NODE_NAME': '%s@1.2.3.4' % repo, 
            'GIGALIXIR_APP_NAME': '', 
            'ERLANG_COOKIE': 'fake-erlang-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'PORT': '4000', 
            'LOGPLEX_TOKEN': '', 
        }