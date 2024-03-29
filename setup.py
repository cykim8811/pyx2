from setuptools import setup, find_packages

setup(
    name='pyx2',
    version='2.0.0',
    description='A framework that enables Python objects to be easily rendered on a web server',
    author='Kim Changyeon',
    author_email='cykim8811@snu.ac.kr',
    requires=[
        'starlette',
        'websockets',
        'uvicorn',
        'pillow',
        'watchdog',
    ],
    # url='https://github.com/cykim8811/pyx-react',
    # package_folder: ./pyx2
    packages=find_packages('src'),
    install_requires=[],
    # entry_points={
        # 'console_scripts': [
        #     'pyx=pyx_transpiler.transpile:transpile_path',
        # ]
    # },
    license='MIT',
    # long_description=open('README.md').read(),
    # long_description_content_type='text/markdown',
    keywords=['pyx', 'react', 'python', 'visualization', 'web', 'fullstack', 'realtime'],
    package_dir = {'': 'src'},
    package_data={'pyx2': ['assets/*']},
)