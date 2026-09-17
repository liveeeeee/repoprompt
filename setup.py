from setuptools import setup

setup(
    name="repoprompt",
    version="1.2.0",
    py_modules=["repoprompt"],
    entry_points={
        "console_scripts": [
            "repoprompt=repoprompt:main",
        ],
    },
)
