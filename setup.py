from setuptools import setup, find_packages


def read_file(name):
    with open(name) as fd:
        return fd.read()


setup(
    name='django-sql-utils',
    version='0.2.0',
    description='Improved API for aggregating using Subquery',
    long_description=read_file('README.rst'),
    url='https://github.com/martsberger/django-sql-utils',
    download_url='https://github.com/martsberger/django-sql-utils/archive/0.2.0.tar.gz',
    author='Brad Martsberger',
    author_email='bmarts@lumere.com',
    license='MIT',
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    packages=find_packages(),
    install_requires=['django>=1.11']
)