FROM python:3.13

# Install SSH client
RUN apt-get update && apt-get install -y openssh-client

# Set env variables
ENV PYTHONUNBUFFERED 1

# Set the working directoy
WORKDIR /app

# Copy requirements.txt file
COPY requirements.txt /app/requirements.txt

# Install python dependencies
RUN pip install -r requirements.txt

# Copy app to working directory
COPY . /app

# Start the SSH tunnel
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
