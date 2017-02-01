from extronlib.interface import EthernetServerInterfaceEx
from extronlib.system import File
import time
import re
import datetime


class WebServer(EthernetServerInterfaceEx):
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)  # Init the Server object
        self._HTTP_Header = self._UpdateHTTPHeader()  # Updates the date/time on the HTTP header to current time
        self._PAGE_NOT_FOUND_404 = self.Set(
            '404Page')  # Sets the default 404 page. (The 404 page is displayed when a browser request a page that doesnt exist.)
        self._NewRequestCallback = None  # The callback is called whenever a new request is recieved from a browser. The callback should accept 2 parameters. The web server object and a request object.
        self.ReceiveData = self._ReceiveData
        self.DefaultPage = None  # If set, the default page will be sent to the browser if it doesnt request a specific page.

        print(self.StartListen(), 'on port', self.IPPort)  # Start the web server listening for request from browsers.

    def _UpdateHTTPHeader(self):
        # Updates the date/time on the HTTP header to current time
        self._HTTP_Header = '''HTTP/1.1 200 OK
            Date: {}
            Connection: close
            Server: GlobalScripter
            Content-Type: text/html

            '''.format(time.asctime()).encode()
        return self._HTTP_Header

    def Set(self, command=None, value=None, qualifier=None):
        '''
        command = '404Page' or 'DefaultPage'.
        This method will probably support more commands in the future.

        Examples:
        WebServer.Set('404Page', '404.html') #You can load a custom 404.html page via SFTP and this will now be used as the default 404 page.
        WebServer.Set('DefaultPage', 'default.html') #If a browser request no specific page, default.html will be returned.
        '''
        if command == '404Page':
            if value == None:
                PAGE_NOT_FOUND_404 = b'''
                    <html>
                    	<title>
                    		404 PAGE NOT FOUND
                    	</title>
                    	<body>
                    		404 PAGE NOT FOUND
                    	</body>
                    </html>
                    '''
                self._PAGE_NOT_FOUND_404 = PAGE_NOT_FOUND_404

            else:
                try:
                    self.Response404 = File(value, mode='rb').read()
                except Exception as e:
                    print(e)

        elif command == 'DefaultPage':
            self.DefaultPage = value

    def SubscribeStatus(self, command, qualifier=None, callback=None):
        '''
        command = 'NewRequest' #probably support more in the future
        '''
        if command == 'NewRequest':
            # The web server will now call callback(self, request) whenever a request is received from a browser
            self._NewRequestCallback = callback

    def _ReceiveData(self, client, data):
        # print('_ReceiveData(client={}, data={})'.format(client, data))
        if type(data) == bytes:
            data = data.decode()

        req = Request(client, data,
                      webserver=self)  # Creates a Request object which parses the data in the request and allows the programmer easy access to the parsed data.

        if self._NewRequestCallback is not None:
            self._NewRequestCallback(self, req)
        else:
            self.RespondNormally(req)

    def SendResponse(self, request, response):
        ''' This method sends a custom response and adds a header

        request = Request object that the response is responding to.
        response = raw HTML code. Headers will be automatically added.

        Example:
        Content = '\
            <html>\
                <body>\
                    This is the response body from main.py at {}\
                </body>\
            </html>\
            '.format(time.asctime())

        request.SendResponse(Content)
        '''
        response = self._UpdateHTTPHeader() + response
        self.SendRawResponse(request, response)

    def SendRawResponse(self, request, response):
        # This method sends a raw HTTP response and does not add any HTTP headers
        request.client.Send(response)
        try:
            request.client.Disconnect()
            # For some reason the .Disconnect method causes and error, but works correctly on IPCP FW 2.3
        except Exception as e:
            pass

    def RespondNormally(self, request):
        client = request.client

        if request.PageRequested == '':

            # If no specific page is requested, then show the default page if it has been set.
            if self.DefaultPage is not None:
                responseFile = File(self.DefaultPage, mode='rb')
                client.Send(responseFile.read())

            else:
                responseFile = File(self._PAGE_NOT_FOUND_404, mode='rb')
                client.Send(responseFile.read())

        else:

            try:
                responseFile = File(request.PageRequested, mode='rb')
                client.Send(responseFile.read())
            except:
                client.Send(self._PAGE_NOT_FOUND_404)

        try:
            client.Disconnect()
        except:
            pass


class Request():
    '''
    A Request object parses the raw HTTP data and stores it.
    This allows the programmer easy access to info about the request, such as name-value-pairs.
    '''
    RequestInfoRegex = re.compile('(GET|POST) \/(.{0,}) HTTP')
    BodyRegex = re.compile('\r\n\r\n(.{0,})')

    def __init__(self, client, raw, webserver):
        # raw = str
        self.client = client
        self.raw = raw
        self.NVPs = {}
        self.Type = 'Unknown'
        self.PageRequested = None
        self.webserver = webserver

        # Get the pagename and NVPs if available (NVP= Name-Value-Pair. Example 'email=gmiller@extron.com&password=SuperSecretPasswordOfDoom')
        RequestInfoMatch = self.RequestInfoRegex.search(self.raw)
        if RequestInfoMatch:
            self.Type = RequestInfoMatch.group(1)

            pageInfo = RequestInfoMatch.group(2)  # Example: 'index.html?action=helloworld' or 'favicon.ico'
            if '?' in pageInfo:
                split = pageInfo.split('?')
                self.PageName = split[0]

                nameValuePairsRaw = split[1]
                NVPs = nameValuePairsRaw.split('&')
                for NVP in NVPs:
                    name, value = NVP.split('=')
                    self.NVPs[name] = value
                    # print('self.NVPs=', self.NVPs)
            else:
                self.PageName = pageInfo

            self.PageRequested = self.PageName
            # print('self.PageRequested=', self.PageRequested)

        # Search body for NVPs (HTTP POSTs have NVPs in body)
        if self.Type == 'POST':
            BodyMatch = self.BodyRegex.search(self.raw)
            if BodyMatch:
                NVPstring = BodyMatch.group(1)
                NVPList = NVPstring.split('&')
                for NVP in NVPList:
                    name, value = NVP.split('=')
                    self.NVPs[name] = value
                    # print('self.NVPs=', self.NVPs)

        # Search header for cookies or other NVPs
        # print('search for header. self.raw=', self.raw)
        RawHeader = self.raw.split('\r\n\r\n')[0]
        RawHeaderLines = RawHeader.split('\r\n')
        for RawLine in RawHeaderLines:
            if ':' in RawLine:
                name, value = RawLine.split(': ')
                if name != 'Cookie':
                    self.NVPs[name] = value
                else:
                    cookies = value.split('; ')
                    for cookie in cookies:
                        name, value = cookie.split('=')
                        self.NVPs[name] = value

                        # print('self.NVPs=', self.NVPs)

    def GetValue(self, name):
        '''
        Returns name-value-pair info.

        Example:
        The browser request 1.1.1.1:8080?hello=world

        val = RequestObj.GetValue('hello')
        print(val)
        >>'world'

        '''
        return self.NVPs.get(name)

    def Set(self, command, value, qualifier=None):
        # allows the programmer to force a certain response
        # Can also use: WebServerObj.SendResponse(CustomHTMLhere)

        if command == 'Response':
            try:
                value = value.encode()
            except Exception as e:
                print(e)
                raise e

            self.client.Send(value.encode())

    def get_method(self):
        # Returns 'GET' or 'POST'
        # See the difference here http://www.w3schools.com/TAGs/ref_httpmethods.asp
        return self.Type

    def has_data(self):
        # Returns True/False if the request contains name-value-pairs
        if self.NVPs != {}:
            return True
        else:
            return False

    def get_data(self):
        # Returns all name-value-pairs as dict
        return self.NVPs


class Response():
    '''
    This object represents an HTTP response.

    This object gives the programmer an easy API for the following:
        Add HTTP Cookies
        Replace text in the HTML via javascript
        Replace sections of HTML via AJAX
        Auto refresh the page at regular intervals
        Add javascript redirect to another page/website
        Save response HTML to a file.

    '''

    def __init__(self, webserver, requestObj, templateFile=None, ):
        '''
        requestObj = Request object that this Response object is in reference to

        '''
        self.request = requestObj
        self.webserver = webserver

        try:
            self.templateFile = open(templateFile).read()
        except:
            # The template file does not exist
            if templateFile == None:
                templateFile = '''
            <html>
              <body>

              </body>
            </html>
            '''
            elif isinstance(templateFile, str):
                self.templateFile = templateFile

        if '<head' not in self.templateFile:
            # the template needs a <head> section so the javascripts can be placed there.
            BodyStart = self.templateFile.find('<body')
            self.templateFile = self.templateFile[:BodyStart] + '\n<head></head>\n' + self.templateFile[BodyStart:]

        self.scripts = []
        self.cookies = []
        self.numberOfScripts = 0
        self.Cache = False
        self.AutoRefresh = False
        # self.LogUsers()

    def AJAXReplace(self, jsID='', replacementURL=''):
        '''This method will replace the section of HTML with javascript id = jsID.
        This uses AJAX. Learn more here: http://www.w3schools.com/php/php_ajax_intro.asp

        For example if you have a part of your HTML like this:
            <span id='ThisIsMyJavaScriptID'>Hello</span>

        And you call
            ResponseObj.AJAXReplace(jsID = 'ThisIsMyJavaScriptID', replacementURL = 'www.google.com')

        Your browser page will now show the google home page in the middle of your page
            where it used to say 'Hello'.
            (Note: this is a poor example and will probably mess your browser up royally).
        '''

        self.numberOfScripts += 1
        AJAXRequest = '''
        var xmlhttp''' + str(self.numberOfScripts) + ''' = new XMLHttpRequest();
          xmlhttp''' + str(self.numberOfScripts) + '''.onreadystatechange = function() {
            if (xmlhttp''' + str(self.numberOfScripts) + '''.readyState == 4 && xmlhttp''' + str(self.numberOfScripts) + '''.status == 200) {
              document.getElementById("''' + jsID + '''").innerHTML = xmlhttp''' + str(self.numberOfScripts) + '''.responseText;
              };
            };
            xmlhttp''' + str(self.numberOfScripts) + '''.open("GET", "''' + replacementURL + '''", true);
            xmlhttp''' + str(self.numberOfScripts) + '''.setRequestHeader("Content-type","application/x-www-form-urlencoded");
            xmlhttp''' + str(self.numberOfScripts) + '''.send();
        '''
        self.scripts.append(AJAXRequest)

    def TextReplace(self, jsID, text=''):
        '''This method will replace the section of HTML with javascript id = jsID.
        This uses javascript. Learn more here: http://www.w3schools.com/php/php_ajax_intro.asp

        For example if you have a part of your HTML like this:
            <span id='ThisIsMyJavaScriptID'>Hello</span>

        And you call
            ResponseObj.AJAXReplace(jsID='ThisIsMyJavaScriptID', replacement='World')

        Your browser page will now read 'World' where it used to say 'Hello'.
        '''

        text = text.replace('\n', '\\\n')
        script = '''
        document.getElementById("''' + str(jsID) + '''").innerHTML = "''' + str(text) + '''"
        '''
        # print('script=', script)#debuggin
        self.numberOfScripts += 1
        self.scripts.append(script)

    def AddCookie(self, CookieKey='', CookieValue=''):
        # This method adds a cookie to your response.
        # a well-behaved browser will present this cookie with every request on this web page

        # Need to make setCookie function

        self.cookies.append(MakeCookie(self.webserver, self.request, CookieKey, CookieValue))

    def AddJS(self, js):
        # Allows the programmer to add javascript directly.
        self.scripts.append(js)

    def InsertHTML(self, HTML):
        # not sure if this is useful
        self.templateFile = self.templateFile + HTML

    def SetAutoRefresh(self, time):
        '''
        time = time in seconds to auto refresh
        time = 0 means dont refresh
        '''
        if time <= 0:
            time = 0

        self.AutoRefresh = time

        if time > 0:
            js = '''function refresh() {
                    window.location.reload(true);
                    }
                  setTimeout(refresh, ''' + str(time * 1000) + ''');
               '''

            self.AddJS(js)

    def Redirect(self, RedirectURL=''):
        # redirects the browser to a differnt page. can be used to redirect to a different website entirely or to another page within this site.
        js = 'window.location= "' + RedirectURL + '";'
        self.AddJS(js)

    def _CreateResponse(self, withHeaders=True):

        if withHeaders == True:
            # Add the HTTP header.
            response = '''HTTP/1.1 200 OK
                Date: {}
                Connection: close
                Server: GlobalScripter
                Content-Type: text/html'''.format(time.asctime())

            # Add cookies if needed.
            if len(self.cookies) > 0:
                for cookie in self.cookies:
                    response += '\r\n' + cookie

            response += '\r\n'  # Necessary, dont remove. This signals the end of the HTTP Header and the beginning of the HTTP Body.

        else:
            response = ''

        # Add in the JS scripts.
        AllScripts = '''
        <script>
          function Initialize(){
          '''
        for script in self.scripts:
            AllScripts += '\r\n' + script

        AllScripts += '''}
        </script>
        '''

        # Append the rest of the template file after the AJAX scripts.
        NewTemplate = self.templateFile
        NewTemplate = NewTemplate.replace('<body', '<body onload="Initialize();"')
        HeadEnd = NewTemplate.find('</head')
        response += '\r\n' + NewTemplate[:HeadEnd] + AllScripts + NewTemplate[HeadEnd:]

        return response

    def Send(self):
        # Send the HTTP response to the client
        response = self._CreateResponse()
        self.webserver.SendRawResponse(self.request, response)

    def SaveToFile(self, filename):
        # This method saves a http response to a file
        response = self._CreateResponse(withHeaders=False)

        with File(filename, mode='wt') as file:
            file.write(response)
            file.close()


# Helper functions **************************************************************

def MakeCookie(webserver, request, key, value, expiration=None):
    '''
    "expiration" = time in seconds that the cookie is valid.
    Default is 1 year or 31,536,000 seconds
    For example:
    If you want the cookies to be valid for 24hrs, use:
      setCookies('theKey','theValue',60*60*24)
    '''

    domain = request.GetValue('Host')
    # print('domain =', domain)

    if expiration == None:
        expiration = 60 * 60 * 24 * 365  # 1 year

    NextYear = datetime.date.fromtimestamp(time.time() + expiration)
    timeString = NextYear.strftime('%a, %d-%b-%Y %H:%M:%S PST')
    # example timeString = 'Thu, 23-Nov-2017 00:00:00 PST'

    expireString = 'Expires={};'.format(timeString)

    cookieString = ''
    cookieString += 'Set-Cookie:{}={};{}'.format(key, value, expireString)
    if domain is not None:
        cookieString += "\nSet-Cookie:Domain={};{}".format(domain, expireString)
    cookieString += "\nSet-Cookie:Path=/;{}".format(expireString)

    return cookieString


