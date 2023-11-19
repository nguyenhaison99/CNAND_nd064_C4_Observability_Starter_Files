# Use the official Python image.
# https://hub.docker.com/_/python
FROM python:3.7-slim

# Set the working directory in the container.
ENV APP_HOME /app
WORKDIR $APP_HOME

# Copy the local code to the container image.
COPY . ./

# Install production dependencies.
RUN apt-get update && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Command to run the application using Gunicorn.
CMD ["gunicorn", "--access-logfile", "-", "--error-logfile", "-", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]
