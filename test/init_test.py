# This Python file uses the following encoding: utf-8
import os
from sure import expect
import subprocess
import click
from click.testing import CliRunner
import httpretty
import gigalixir_run
import mock

def mocked_open(*args, **kwargs):
    if args == ("/kube-env-vars/REPO", 'r'):
        return mock.mock_open(read_data="my_app").return_value
    else:
        return mock.mock_open().return_value

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
    elif args[0] == 'fake-slug-url':
        return MockResponse(None, 200)

    return MockResponse(None, 404)

@mock.patch('gigalixir_run.open', side_effect=mocked_open)
@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('gigalixir_run.subprocess')
@mock.patch('gigalixir_run.os')
@mock.patch('tarfile.open')
@httpretty.activate
def test_logout(mock_tarfile, mock_os, mock_subprocess, mock_get, mock_open):
    stdin = mock.Mock(nmae='stdin')
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
            'MY_NODE_NAME': 'my_app@', 
            'GIGALIXIR_APP_NAME': '', 
            'ERLANG_COOKIE': 'fake-erlang-cookie', 
            'LC_ALL': 'en_US.UTF-8', 
            'FOO': '1\n2', 
            'PORT': '4000', 
            'LOGPLEX_TOKEN': '', 
            'VMARGS_PATH': '/release-config/vm.args'
        }
