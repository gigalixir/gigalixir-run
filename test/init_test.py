# This Python file uses the following encoding: utf-8
import os
from sure import expect
import subprocess
import click
from click.testing import CliRunner
import httpretty
import gigalixir_run

@httpretty.activate
def test_logout():
    runner = CliRunner()
    # Make sure this test does not modify the user's netrc file.
    with runner.isolated_filesystem():
        os.environ['HOME'] = '.'
        # result = runner.invoke(gigalixir.cli, ['logout'])
        # assert result.output == ''
        # assert result.exit_code == 0
        assert 1 == 2

