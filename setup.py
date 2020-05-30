from setuptools import setup, find_packages

setup(
    name='cfrun',
    version='0.1.0',
    description='Competition programming runner',
    author='Sergey Salnikov',
    author_email='serg@salnikov.ru',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    install_requires=[
        'browser-cookie3',
        'bs4',
        'requests',
        'requests_cache',
        'watchdog',
    ],
    entry_points={
        'console_scripts': [
            'cfrun=cfrun:main',
        ],
    },
)
