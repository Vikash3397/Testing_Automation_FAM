import paramiko
import time

class SSHLibrary:
    def __init__(self, hostname, username, password=None, key_filename=None):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.client = None
        self.channel = None

    def connect(self):
        try:
            # Create an SSH client
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect to the SSH server with password or key
            if self.password:
                self.client.connect(self.hostname, username=self.username, password=self.password)
            elif self.key_filename:
                self.client.connect(self.hostname, username=self.username, key_filename=self.key_filename)
            else:
                raise ValueError("Either password or key_filename must be provided for authentication")

            print("Connected to SSH server")

            # Open an SSH channel
            self.channel = self.client.invoke_shell()

            # Wait for the prompt
            self.wait_for_prompt()

        except Exception as e:
            # Handle any exceptions that occurred during connection
            print(f"Error connecting to SSH server: {e}")

    def execute_command(self, command):
        try:
            # Send the command to the SSH channel
            self.channel.send(command + "\n")

            # Check if any data is available for receiving
            while not self.channel.send_ready():
                pass

            # Wait for the command output until the prompt ('$') appears
            output = ""
            prompt = "$"  # Customize the prompt as needed
            time.sleep(1)

            while not output.strip().endswith(prompt):
                resp = self.channel.recv(4096).decode()
                output += resp

            # Print the command output
            print("SSH command executed",command)
            print("+++++++++++++++++++")
            print("The output is:")

            return output

        except Exception as e:
            # Handle any exceptions that occurred during command execution
            print(f"Error executing SSH command: {e}")

    def wait_for_prompt(self):
        # Wait for the prompt ('$') to appear in the output
        prompt = "$"  # Customize the prompt as needed
        buffer = ""

        while not buffer.strip().endswith(prompt):
            # Check if any data is available for receiving
            while not self.channel.send_ready():
                pass

            resp = self.channel.recv(4096).decode()
            buffer += resp

    def close(self):
        # Close the SSH channel and client
        self.channel.close()
        self.client.close()

# Example usage:
# For password-based authentication
# ssh = SSHLibrary("hostname", "username", "password")
# ssh.connect()
# ssh.execute_command("your_command")
# ssh.close()

# For key-based authentication
# ssh = SSHLibrary("10.61.1.230", "ec2-user", key_filename="C:/Users/radaru01/Desktop/ROBO Projects/COMCAST/Robotframework/Resources/pvt_ky")
# ssh.connect()
# ssh.execute_command("docker exec -t -i 7cfc872897ef /bin/bash")
# ssh.execute_command("sudo su - svwdev")
# ssh.execute_command("sv_status")
# ssh.close()
