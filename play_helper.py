"""
Contains helper methods for the server and client operations.
"""

def parseInt(num, default=0):
    return default if not num or not num.isdigit() else int(num)

def isTrue(value):
    return value and isinstance(value, str) and value.lower() == 'true'