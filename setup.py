from setuptools import setup, find_packages

setup(
    name='gigalixir_run',
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

        # needed for requests, but why isn't it installed through requests's dependencies? maybe upgrading requests will fix this and then we can remove these lines
        # something to do with this?
        # https://github.com/psf/requests/blob/v2.13.0/setup.py#L98
        # cryptography comes from click
        'idna==3.1',
        'pyOpenSSL==20.0.1',

        # I guess this is required to peg six to 1.9.0 
        # which rollbar requires.
        # TODO: after upgrading to python3, remove this and upgrade rollbar
        'six~=1.9.0',

        'pystache~=0.5.4',
    ],
    entry_points='''
        [console_scripts]
        gigalixir_run=gigalixir_run:cli
    ''',
    extras_require={
        'dev': [
            'pytest==3.1.3',
            'mock~=3.0.5',
            'HTTPretty',
            'sure',
        ],
    }

)
