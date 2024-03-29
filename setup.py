from setuptools import setup

required_libraries = [
    "lyricsgenius",
    "beautifulsoup4==4.6.0",
    "faker",
    "jupyter",
    "matplotlib",
    "pandas",
    "requests",
    "lxml",
    "seaborn",
    "scikit-learn",
    "openai",
    "twilio",
    "flask",
    "pyngrok",
    "keras",
    "tensorflow",
    "scipy==1.4.1",
    "numpy==1.18.5",
    "selenium",
    "orjson==3.3.1",
    "boto3==1.14.44",
    "botocore==1.17.44",
    "s3fs",
    "tqdm",
    "pycld3",
    "phyme"
]

setup(
    name="doom",
    version="0.0.1",
    description="the villain with the illest flow in all of mexico",
    url="http://github.com/jattenberg/doom",
    author="jattenberg",
    author_email="josh@attenberg.org",
    license="MIT",
    packages=["doom"],
    zip_safe=False,
    install_requires=required_libraries,
)
