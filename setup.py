from setuptools import find_packages, setup
setup(
    name='mcqgenerator',
    version='0.1.0',     
    author='Shorya Modgil',
    author_email="modgilshorya7@gmail.com",
    install_requires=["openai", "langchain", "streamlit", "python-dotenv","PyPDF2"],
    packages=find_packages(),
)