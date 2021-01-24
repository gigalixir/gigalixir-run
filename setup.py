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

            # needed to avoid error when installing, see
            # https://stackoverflow.com/questions/34819221/why-is-python-setup-py-saying-invalid-command-bdist-wheel-on-travis-ci
            'wheel',
        ],
    }

)
