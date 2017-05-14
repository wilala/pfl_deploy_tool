# -*- coding: utf-8 -*-
from tinydb import TinyDB,where
import logging
import paramiko
import os
import sys
import time
import socket
import getpass

###define log
separator = os.sep
if os.path.exists("log") == False:
    os.mkdir('log')
log_file = "."+separator+"log"+separator+"tools_output.log"
logging.basicConfig(level=logging.DEBUG,filename=log_file,filemode='w',format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s')

###parameters: the target package, env info(type dictionary)
def upload(package,env):
    ip = env.get('ip')
    user = env.get('user')
    password = env.get('password')
    path = env.get('path')
    
    p=paramiko.Transport((ip,22))
    p.connect(username=user,password=password)
    sftp=paramiko.SFTPClient.from_transport(p)
    local_path=os.getcwd()
    local_file=package
    remote_file=path+'/'+package
    print('start upload file... \n'+local_file)
    sftp.put(local_path+separator+local_file,remote_file)
    p.close()


def deploy(package,env,app_cmd,db_cmd):
    env_name = env.get('env_name')
    ip = env.get('ip')
    user = env.get('user')
    password = env.get('password')
    path = env.get('path')
    type = env.get('type')
    db_user = env.get('db_user')
    db_password = env.get('db_password')
    error_info = ''
    
    def get_file(path):
        p=paramiko.Transport((ip,22))
        p.connect(username=user,password=password)
        sftp=paramiko.SFTPClient.from_transport(p)
        print('get log file... \n')
        files = sftp.listdir(path)
        
        #separator = os.sep
        for f in files:
            if os.path.splitext(f)[1] == '.log':
                target_file = path+'/'+f
                sftp.get(target_file,'log'+separator+env_name+"_"+f)
        p.close()
    
    deploytime = time.localtime()
    deploytime_convert = time.strftime("%Y%m%d%H%M%S",deploytime)
    package_name = os.path.splitext(package)[0]
    deploy_folder = deploytime_convert+'_'+package_name
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username =user, password =password)
    
    #db_cmd = 'cd '+path+'\npackage_name=`date +%Y%m%d%H%M`'+package_name+'\n unzip '+package+' -d $package_name'+'\n cd $package_name/db'+'\n sh upgrade_db.sh '+db_user+' '+db_password+'\n'
    #app_cmd = cd '+path+'\npackage_name=`date +%Y%m%d%H%M`_'+package_name+'\n unzip '+package+' -d $package_name'+ '\ncd $package_name/scripts'+'\n sh install.sh upgrade\n' 
    #db_cmd = "cd {0}\n package_name=`date +%Y%m%d%H%M`_{1} \n unzip {2} -d $package_name \n cd $package_name\db \n sh upgrade_db.sh {3} {4} \n".format(path,package_name,package,db_user,db_password)
    #db_cmd = "cd {0};unzip {1} -d {2};cd {2}/db;sh upgrade_db.sh {3} {4}".format(path,package,deploy_folder,db_user,db_password)
    #app_cmd = "cd {0};unzip {1} -d {2};cd {2}/scripts; sh install.sh upgrade".format(path,package,deploy_folder)
    
    app_cmd_exec = app_cmd.format(path=path,package=package,deploy_folder=deploy_folder)
    db_cmd_exec = db_cmd.format(path=path,package=package,deploy_folder=deploy_folder,db_user=db_user,db_password=db_password)
    if type == 'db':
        stdin, stdout, stderr = ssh.exec_command(db_cmd_exec)
        error_info = stdout.channel.recv_exit_status()
        #print(stdout.read())
        ssh.close()
        log_path = path+'/'+deploy_folder+'/db'
        get_file(log_path)
    elif type == 'app':
        stdin, stdout, stderr = ssh.exec_command(app_cmd_exec)
        error_info = stdout.channel.recv_exit_status()
        #print(stdout.read())
        ssh.close()
        log_path = path+'/'+deploy_folder+'/scripts'
        get_file(log_path)
    else:
        print("The type should be 'app' or 'db'!")
        ssh.close()
        error_info = 'ERROR'
        return error_info
        sys.exit()
    return error_info


###get env info and cmd from file "env.json"
def get_env(env_name):
    '''return the map class, element is dictionary of env info'''
    if os.path.exists('env.json') == 0:
        print("Can't find file env.json")
        sys.exit()
    else:
        db = TinyDB('env.json')
        table_env = db.table('env_info')
        table_cmd = db.table('cmd')
        def search_info(env):
            result = table_env.search(where('env_name')==env)
            return result[0]
        app_cmd = table_cmd.all()[0].get('app_cmd')
        db_cmd = table_cmd.all()[1].get('db_cmd')
        if app_cmd == None or db_cmd == None:
            print('app or db cmd can not be empty!')
        else:
            return map(search_info,env_name),app_cmd,db_cmd


######## open secureCRT to connect target environment
def open_crt(env):
    env_name = env.get('env_name')
    ip = env.get('ip')
    user = env.get('user')
    password = env.get('password')
    path = env.get('path')
    conn_str = '''
# $language = "python"
ip = '{ip}'
user = '{user}'
password = '{password}'
path = '{path}'
def main():
    cmd = "/SSH2 /L %s /PASSWORD %s /C 3DES /M MD5 %s" % (user, password, ip)
    crt.Session.Connect(cmd)
    crt.Screen.Send("cd %s \\n" % (path))
main()
    '''
    if os.path.exists('crt_path.txt'):
        with open('crt_path.txt','r') as f:
            crt = f.readline()
    else:
        crt = input('Please the full path of crt(D:\SecureCRT\SecureCRT.exe):\n')
        with open('crt_path.txt','w') as f:
            f.writelines(crt)    
    with open(env_name+'_CRTconnect.py','w') as conn_file:
        conn_file.writelines(conn_str.format(ip=ip,user=user,password=password,path=path))
    #crt_str = 'SecureCRT.exe /SCRIPT '+env_name+'_CRTconnect.py'
    crt_cmd = crt+ ' /SCRIPT '+env_name+'_CRTconnect.py'
    try:
        os.system(crt_cmd)
    except:
        print("Can't found SecureCRT on you computer! Exit")
        sys.exit()
######## open secureCRT ##end

######## Getting package from ftp
ftp_host = "ftp.ebaotech.com"
user = "pfl"
password = "M5j9Ks3T"


class sftp:
    def __init__(self, ftp_host, user, password):
        self.ftp_host = ftp_host
        self.user = user
        self.password = password
        self.ts = paramiko.Transport(ftp_host,22)
    def open(self):
        self.ts.connect(username = self.user, password = self.password)
        sftp_object = paramiko.SFTPClient.from_transport(self.ts)
        return sftp_object
    def close(self):
        self.ts.close()

def get_lastest_file(path, ftp_object):
    #### temp
    max_mtime = 0
    lastest_file = paramiko.sftp_attr.SFTPAttributes()
    current_path = path
    target = ""
       
    #### compare modify time to get lastest file in current folder
    files = ftp_object.listdir_attr(current_path)
    for f in files:
        if f.st_mtime > max_mtime:
            max_mtime = f.st_mtime
            lastest_file = f
    
    #### folder's st_mode is 16877, file is 33188                        
    if lastest_file.st_mode == 16877:
        next_path = path + '/' + lastest_file.filename
        get_lastest_file(next_path, ftp_object)
    elif lastest_file.st_mode == 33188:
        target = current_path+'/'+lastest_file.filename
        print(target)
        return current_path+'/'+lastest_file.filename
    else:
        return None

pfl_sftp = sftp(ftp_host,user,password)
connection = pfl_sftp.open()

package = get_lastest_file('/pfl', connection)
pfl_sftp.close()
if package != None:
    print(package)           ###待优化，提供选项，确认或者手工输入发布包路径
else:
    print("Not found target file or lastest modfiied folder is empty!")

######## compare package name with environment name
def compare(str1,str2):
    #####获取最长公共子串
    str1 = str1.lower()
    str2 = str2.lower()
    record_list = [] ####取str2中字母和str1比较，记录结果到该list
    max_num = [] #####记录每比较一次后的最大值
    for i in str1:
        record_list.append(0)
    index2 = 0
    for character2 in str2:
        index1 = len(str1)
        for character1 in str1[::-1]:
            index1 = index1 - 1
            if character2 == character1:
                if index2 > 0 and index1 >0 :
                    record_list[index1] = record_list[index1-1] + 1
                else:
                    record_list[index1] = 1
            else:
                record_list[index1] = 0    
        index2 = index2 + 1
        max_num.append(max(record_list))        
    return max(max_num)

def match_target_env(package):
    db = TinyDB('env.json')
    table_env = db.table('env_info')
    envs= {}
    for i in table_env.all():
        envs[i.get('env_name')] = compare(i.get('env_name'),package)
    target = []
    for a,b in envs.items():
        if b == max(envs.values()):
            max_value_env.append(a)
    target.sort()
    target.reverse()
    return target


######## Main Steps
#package = sys.argv[1]
#env_name = sys.argv[2:]
if os.path.exists(os.getcwd()+separator+package) and len(env_name) > 0:
    envs,app_cmd,db_cmd = get_env(env_name)
    print("start deploying %s to :" %(package))
    for env in envs:
        print(env.get('env_name'))
        print(env.get('ip')+'\n')
        upload(os.getcwd()+separator+package,env)
        error_info = deploy(os.getcwd()+separator+package,env,app_cmd,db_cmd)
        if error_info:
            print("Found error,try to login target server\n\n")
            open_crt(env)
        else:
            print('Success!!')        
        print('\n')
else:
    print("Package does not exists or target environment is empty, abort.")
    sys.exit()