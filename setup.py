#!/usr/bin/env python2

from distutils.core import setup

setup(name='lxnstack',
      version='1.5.0',
      description='',
      author='Maurizio D\'Addona',
      author_email='mauritiusdadd@gmail.com',
      url='https://sites.google.com/site/lxnstack/home',
      provides=['lxnstack'],
      requires=['scipy', 'numpy', 'cv2'],
      packages=['lxnstack'],
      package_data={'lxnstack': ['data/*', 'data/icons/*',
                                 'data/ui/*', 'data/lang/*',
                                 'data/styles/*']},
      data_files=[('share/licenses/lxnstack', ['COPYRIGHT']),
                  ('share/applications', ['mime/lxnstack.desktop']),
                  ('share/lxnstack/', ['mime/lxnstack-project.xml',
                                       'mime/lxnstack.png']),
                  ],
      scripts=['scripts/lxnstack']
      )
