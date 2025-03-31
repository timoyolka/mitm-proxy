For now, this proxy only forwards traffic between the client and the target, it has the ability to intercept the traphic,
because all the connections are established with tls,
this project is async, it means it is very efficient and has only one thread and can support thousand of connections,
you can run it by setting your windows proxy settings to your local host on port 8080, (127.0.0.1:8080)
The project is relativly simple, and not requires external libraries except: cryptography==44.0.2
Before running your project make sure you run: "pip install cryptography".
