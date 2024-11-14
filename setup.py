import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="gradescope-api",
    version="0.0.3",
    author="Rei Doko",
    author_email="dokorei@msu.edu",
    description="An unofficial Gradescope API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/reidoko/gradescope-api",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.6",
    install_requires=["requests", "bs4", "pytz"],
)
