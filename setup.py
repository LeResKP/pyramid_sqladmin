from setuptools import setup, find_packages
import sys, os

version = '0.0'

setup(name='pyramid_sqladmin/',
      version=version,
      description="Simple way to edit your SQLAlchemy objects in pyramid",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Aur\xc3\xa9lien Matouillot',
      author_email='a.matouillot@gmail.com',
      url='https://github.com/LeResKP/pyramid_sqladmin',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'sqla_declarative',
          'pyramid',
          'SQLAlchemy',
          'zope.sqlalchemy',
          'tw2.core',
          'tw2.sqla',
      ],
      test_suite = 'nose.collector',
      tests_require=[
          'nose',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
