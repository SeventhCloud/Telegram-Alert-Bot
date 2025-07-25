# Use an official Python runtime as a base image
FROM python:3.11-alpine

# Set the working directory in the container
WORKDIR /app

# Set environment variables for unbuffered Python output
# This is crucial for seeing logs in real-time when running in Docker
ENV PYTHONUNBUFFERED 1

# Copy the requirements file into the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Command to run the application
# Use `python -m bot` to run the module, which is good practice
CMD ["python", "blackhole-bot.py"]