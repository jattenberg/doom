from setuptools import setup

required_libraries = [
    "beautifulsoup4",
    "faker",
    "jupyter",
    "matplotlib",
    "pandas",
    "pymc3==3.9.3",
    "requests",
    "seaborn",
    "scikit-learn",
    "openai",
    "twilio",
    "flask",
    "python-dotenv",
    "pyngrok",
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
