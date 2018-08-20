import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyIOT",
    version="0.1.0",
    author="dhrone",
    author_email="ron@ritchey.org",
    description="Simplifies driver development for Amazon's IOT-Core service",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dhrone/pyIOT",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
