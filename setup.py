from setuptools import setup, find_packages

setup(
    name='gigalixir-run',
    author='Jesse Shieh',
    author_email='jesse@gigalixir.com',
    version='0.1.1',
    packages=find_packages(),
    include_package_data=True,
    data_files=[('templates', ['gigalixir_run/templates/vm.args.mustache'])],
    install_requires=[
        'click~=6.7',
        'requests~=2.13.0',
        'rollbar~=0.13.11',

        # I guess this is required to peg six to 1.9.0 
        # which rollbar requires.
        'six~=1.9.0',

        # heroku/cedar:14 is old. it uses python 2.7.6
        # it needs an ssl upgrade to support SNI.
        'urllib3~=1.20',
        'pyOpenSSL~=17.0.0',
        'cryptography~=1.8.1',
        'idna~=2.5',
        'certifi~=2017.4.17',
        'pystache~=0.5.4',
    ],
    entry_points='''
        [console_scripts]
        gigalixir_run=gigalixir_run:cli
    ''',
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
        'HTTPretty',
        'sure',
    ],
)
