A collection of useful tools for Global Scripter

I'll be honest, there is a bunch of one-off stuff in this module.
You should look through it. They are almost all self contained functions.

My Favorites
============

HashableDict() - Class - You cannot use a dict() object as a key in another dict/set. But you can with this class.

DecodeLiteral - Function - Useful for decoding response from .SendAndWait(). By default python's .decode() uses the utf-8, but we dont always want that.

HashIt() - Function - A quick way to hash a string

IncrementIP() - Function - Increment an IP Address. For example IncrementIP('192.168.254.251') = '192.168.254.252'

IsValidIPv4() - Function - Verifies the ip address is valid

IsValidEmail() - Function - Verify an email address is valid

IsValidHostname() - Function - Verify a hostname is valid
