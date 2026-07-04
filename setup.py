from setuptools import setup, find_packages

setup(
    name="sysmon",
    version="0.2.0",
    description="Terminal system resource monitor — live bar charts, history trends, spike review",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="sysmon contributors",
    license="MIT",
    python_requires=">=3.9",
    install_requires=["psutil>=5.0"],
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "sysmon = sysmon.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Monitoring",
    ],
)
