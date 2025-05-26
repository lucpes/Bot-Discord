FROM python:3
COPY . /app
Run pip install discord
WORKDIR /app
CMD python main.py