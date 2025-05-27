FROM python:3
COPY . /app
Run pip install discord && py-cord python-dotenv
WORKDIR /app
CMD python main.py