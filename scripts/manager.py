
#!/usr/bin/env python3

import sys
import subprocess
import asyncio
import websockets
import os
import threading
import time
import json
import stat
import tempfile
import re
from pylint import epylint as lint

# Function to check if a device exists
def check_device(device_path):
    try:
        return stat.S_ISCHR(os.lstat(device_path)[stat.ST_MODE])
    except:
        return False

DRI_PATH = "/dev/dri/card0"
ACCELERATION_ENABLED = check_device(DRI_PATH)
DRONE_EX = ["drone_cat_mouse", "follow_road", "follow_turtlebot", "labyrinth_escape", "position_control", "rescue_people", "drone_hangar", "drone_gymkhana", "visual_lander", "drone_cat_mouse_game"]
CIRCUIT_EX = ["follow_line", "follow_line_game"]

# Docker Thread class for running commands on threads
class DockerThread(threading.Thread):
    def __init__(self, cmd):
        threading.Thread.__init__(self)
        self.cmd = cmd

    def run(self):
        subprocess.Popen(self.cmd, shell=True, stdout=subprocess.PIPE, bufsize=1024, universal_newlines=True)

    def call(self):
        subprocess.call(self.cmd, shell=True, stdout=subprocess.PIPE, bufsize=1024, universal_newlines=True) 


# Class to store the commands
class Commands:
    # Initialization function
    def __init__(self):
        # Constants
        self.GAZEBO_RESOURCE_PATH = "export GAZEBO_RESOURCE_PATH=/usr/share/gazebo-11:$GAZEBO_RESOURCE_PATH:"
        self.DISPLAY = ":0"

        self.read_json_instructions("instructions.json")

    # Function to read the instructions to run an exercise
    def read_json_instructions(self, path):
        with open(path) as f:
            self.instructions = json.load(f)

    # Function to get the Gazebo Path Variables
    def get_gazebo_path(self, exercise):
        gazebo_path = self.GAZEBO_RESOURCE_PATH + self.instructions[exercise]["gazebo_path"] + ";"
        return gazebo_path

    # Function to get the instructions to run ROS
    def get_ros_instructions(self, exercise, circuit=None):
        if ACCELERATION_ENABLED:
            roslaunch_cmd = '/bin/sh -c "export PWD="/";chmod +rwx /;export DISPLAY=:0;export VGL_DISPLAY=/dev/dri/card0;export OLDPWD=/etc/ros/rosdep;export LD_LIBRARY_PATH=/opt/ros/noetic/lib:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/catkin_ws/devel/lib;export GAZEBO_MODEL_PATH=/usr/share/gazebo-11/models:$GAZEBO_MODEL_PATH;export GAZEBO_MODEL_DATABASE_URI=http://gazebosim.org/models;export ROS_DISTRO=noetic;export PKG_CONFIG_PATH=/opt/ros/noetic/lib/pkgconfig;export OGRE_RESOURCE_PATH=/usr/lib/x86_64-linux-gnu/OGRE-1.9.0;export SHLVL=1;export GAZEBO_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:${GAZEBO_PLUGIN_PATH};export TERM=xterm;export ROS_VERSION=1;export GAZEBO_MASTER_URI=http://localhost:11345;ROS_ETC_DIR=/opt/ros/noetic/etc/ros;export CMAKE_PREFIX_PATH=/opt/ros/noetic;export ROS_PACKAGE_PATH=/opt/ros/noetic/share;chmod +x /opt/ros/noetic/bin/rosmaster; export' \
                'PYTHONPATH=/opt/ros/noetic/lib/python3/dist-packages/;chmod +x /opt/ros/noetic/bin/roslaunch; export' \
                'ROS_ROOT=/opt/ros/noetic/share/ros;export GAZEBO_RESOURCE_PATH=/usr/share/gazebo-11:$GAZEBO_RESOURCE_PATH; export' \
                'ROS_MASTER_URI=http://localhost:11311;export PATH=/opt/ros/noetic/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin;' \
                'export ROS_PACKAGE_PATH=/opt/ros/noetic/share:/PX4-Autopilot:/PX4-Autopilot/Tools/sitl_gazebo:/catkin_ws/src/drone_wrapper:/catkin_ws/src/drone_assets;'
        else:
            roslaunch_cmd = '/bin/sh -c "export PWD="/";chmod +rwx /;export DISPLAY=:0;export OLDPWD=/etc/ros/rosdep;export LD_LIBRARY_PATH=/opt/ros/noetic/lib:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:/catkin_ws/devel/lib;export GAZEBO_MODEL_PATH=/usr/share/gazebo-11/models:$GAZEBO_MODEL_PATH;export GAZEBO_MODEL_DATABASE_URI=http://gazebosim.org/models;export ROS_DISTRO=noetic;export PKG_CONFIG_PATH=/opt/ros/noetic/lib/pkgconfig;export OGRE_RESOURCE_PATH=/usr/lib/x86_64-linux-gnu/OGRE-1.9.0;export SHLVL=1;export GAZEBO_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:${GAZEBO_PLUGIN_PATH};export TERM=xterm;export ROS_VERSION=1;export GAZEBO_MASTER_URI=http://localhost:11345;ROS_ETC_DIR=/opt/ros/noetic/etc/ros;export CMAKE_PREFIX_PATH=/opt/ros/noetic;export ROS_PACKAGE_PATH=/opt/ros/noetic/share;chmod +x /opt/ros/noetic/bin/rosmaster; export' \
                'PYTHONPATH=/opt/ros/noetic/lib/python3/dist-packages/;chmod +x /opt/ros/noetic/bin/roslaunch; export' \
                'ROS_ROOT=/opt/ros/noetic/share/ros;export GAZEBO_RESOURCE_PATH=/usr/share/gazebo-11:$GAZEBO_RESOURCE_PATH; export' \
                'ROS_MASTER_URI=http://localhost:11311;export PATH=/opt/ros/noetic/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin;' \
                'export ROS_PACKAGE_PATH=/opt/ros/noetic/share:/PX4-Autopilot:/PX4-Autopilot/Tools/sitl_gazebo:/catkin_ws/src/drone_wrapper:/catkin_ws/src/drone_assets;'

        gz_cmd = roslaunch_cmd
        roslaunch_cmd = roslaunch_cmd + self.get_gazebo_path(exercise)
        for instruction in self.instructions[exercise]["instructions_ros"]:
            if exercise in DRONE_EX and len(sys.argv)>=2 and sys.argv[1] == "log":
                instruction = instruction + " log"
            elif exercise in CIRCUIT_EX:
                instruction = instruction.format(circuit)
                print('INSTRUCTION: ', instruction)    
            
            if not (ACCELERATION_ENABLED):
                roslaunch_cmd = roslaunch_cmd + instruction + ";"
            else:
                roslaunch_cmd = roslaunch_cmd + "vglrun " + instruction + ";"
        roslaunch_cmd = roslaunch_cmd + '"'
        return roslaunch_cmd, gz_cmd

    # Function to start gzclient
    def start_gzclient(self, exercise, width, height):
        # Configure browser screen width and height for gzclient
        gzclient_config_cmds = ["echo [geometry] > ~/.gazebo/gui.ini;",
                                "echo x=0 >> ~/.gazebo/gui.ini;",
                                "echo y=0 >> ~/.gazebo/gui.ini;",
                                f"echo width={width} >> ~/.gazebo/gui.ini;",
                                f"echo height={height} >> ~/.gazebo/gui.ini;"]

        if not (ACCELERATION_ENABLED):
	    # Write display config and start gzclient
            gzclient_cmd = (f"export DISPLAY={self.DISPLAY};" + self.get_gazebo_path(exercise) + "".join(gzclient_config_cmds) + "gzclient --verbose")
        else:
            gzclient_cmd = (f"export DISPLAY={self.DISPLAY};" +
		    self.get_gazebo_path(exercise) +
		    "".join(gzclient_config_cmds) +
		    "export VGL_DISPLAY=/dev/dri/card0; vglrun gzclient --verbose")
        gzclient_thread = DockerThread(gzclient_cmd)
        gzclient_thread.start()

    # Function to stop gzclient
    def stop_gzclient(self):
        cmd_stop = ['pkill', '-f', 'gzclient']
        self.run_subprocess(cmd_stop)

    # Function to start the console
    def start_console(self, width, height):
        # Write display config and start the console
        width = int(width) / 10; height = int(height) / 18
        console_cmd = f"export DISPLAY=:1;"
        if ACCELERATION_ENABLED:
            console_cmd += f"vglrun xterm -fullscreen -sb -fa 'Monospace' -fs 10 -bg black -fg white"
        else:
            console_cmd += f"xterm -geometry {int(width)}x{int(height)} -fa 'Monospace' -fs 10 -bg black -fg white"

        console_thread = DockerThread(console_cmd)
        console_thread.start()

    # Function to start VNC server
    def start_vnc(self, display, internal_port, external_port):
        if not (ACCELERATION_ENABLED):
            # Start VNC server without password, forever running in background
            x11vnc_cmd = f"x11vnc -display {display} -nopw -forever -xkb -bg -rfbport {internal_port}"
            x11vnc_thread = DockerThread(x11vnc_cmd)
            x11vnc_thread.start()

            # Start noVNC with default port 6080 listening to VNC server on 5900
            novnc_cmd = f"/noVNC/utils/launch.sh --listen {external_port} --vnc localhost:{internal_port}"
            novnc_thread = DockerThread(novnc_cmd)
            novnc_thread.start()
        else:
            # Start VNC server without password, forever running in background
            turbovnc_cmd = f"export VGL_DISPLAY=/dev/dri/card0; export TVNC_WM=startlxde; /opt/TurboVNC/bin/vncserver {display} -geometry '1920x1080' -vgl -noreset -SecurityTypes None -rfbport {internal_port}"
            turbovnc_thread = DockerThread(turbovnc_cmd)
            turbovnc_thread.start()

            # Start noVNC with default port 6080 listening to VNC server on 5900
            novnc_cmd = f"noVNC/utils/launch.sh  --listen {external_port} --vnc localhost:{internal_port}"
            novnc_thread = DockerThread(novnc_cmd)
            novnc_thread.start()

    # Function to stop VNC server for accelerated simulation
    def stop_vnc(self):
        cmd_vnc_0 = ['/opt/TurboVNC/bin/vncserver', '-kill', ':0']
        self.run_subprocess(cmd_vnc_0)
        cmd_vnc_1 = ['/opt/TurboVNC/bin/vncserver', '-kill', ':1']
        self.run_subprocess(cmd_vnc_1)

    # Function to start an exercise
    def start_exercise(self, exercise, circuit=None):
        host_cmd = self.instructions[exercise]["instructions_host"]
        host_thread = DockerThread(host_cmd)
        host_thread.start()

        try:
            gui_cmd = self.instructions[exercise]["instructions_gui"]
            if exercise in CIRCUIT_EX:
                gui_cmd = gui_cmd.format(circuit)
                print('GUI: ',gui_cmd)
            gui_thread = DockerThread(gui_cmd)
            gui_thread.start()
        except KeyError:
            pass

        # Launch exercise_guest.py
        try:
            host_cmd_guest = self.instructions[exercise]["instructions_guest"]
            guest_thread = DockerThread(host_cmd_guest)
            guest_thread.start()
        except KeyError:
            pass

        # Launch gui_guest.py
        try:
            gui_cmd_guest = self.instructions[exercise]["instructions_gui_guest"]
            if exercise in CIRCUIT_EX:
                gui_cmd_guest = gui_cmd_guest.format(circuit)
                print('GUI guest: ',gui_cmd_guest)
            gui_thread_guest = DockerThread(gui_cmd_guest)
            gui_thread_guest.start()
        except KeyError:
            pass

    # Function to start the Xserver
    def start_xserver(self, display):
        xserver_cmd = f"/usr/bin/Xorg -noreset +extension GLX +extension RANDR +extension RENDER -logfile ./xdummy.log -config ./xorg.conf {display}"
        xserver_thread = DockerThread(xserver_cmd)
        xserver_thread.start()

    # Function to roslaunch Gazebo Server
    def start_gzserver(self, exercise, circuit):
        if os.path.exists("/status.txt"):
            os.remove("/status.txt")
        
        if exercise in CIRCUIT_EX:
            roslaunch_cmd, gz_cmd = self.get_ros_instructions(exercise, circuit=circuit)
        else:
            roslaunch_cmd, gz_cmd = self.get_ros_instructions(exercise)
		
        roslaunch_thread = DockerThread(roslaunch_cmd)
        roslaunch_thread.start()
        args=["gz", "stats", "-p"]
        repeat = True
        while repeat:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
            with process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if not ("is not running" in line):
                        repeat = False
                        break
                    else:
                        repeat = True

        if exercise in DRONE_EX:
            data  = ""
            while True:
                try:
                    with open("/status.txt", "r", encoding="utf-8") as f:
                        data = f.read(4)
                    if data == "done":
                        os.remove("/status.txt")
                        break
                except:
                    time.sleep(2)

    def start_stdrserver(self,exercise):
        roslaunch_cmd,gz_cmd = self.get_ros_instructions(exercise)
        roslaunch_thread = DockerThread(roslaunch_cmd)
        roslaunch_thread.start()

    # Function to pause Gazebo physics
    def pause_physics(self):
        cmd = "/opt/ros/noetic/bin/rosservice call gazebo/pause_physics"
        rosservice_thread = DockerThread(cmd)
        rosservice_thread.call()

    # Function to unpause Gazebo physics
    def unpause_physics(self):
        cmd = "/opt/ros/noetic/bin/rosservice call gazebo/unpause_physics"
        rosservice_thread = DockerThread(cmd)
        rosservice_thread.call()

    # Function to reset Gazebo physics
    def reset_physics(self, simulator):
        if (simulator == "gazebo"):
            cmd = "/opt/ros/noetic/bin/rosservice call gazebo/reset_world"
            rosservice_thread = DockerThread(cmd)
            rosservice_thread.call()
        else:
            cmd = "rosrun stdr_robot robot_handler replace /robot0 4 8 0"
            rosservice_thread = DockerThread(cmd)
            rosservice_thread.start()


    # Function to start subprocess
    def run_subprocess(self, cmd):
        subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)

    # Function to wait subprocess
    def call_subprocess(self, cmd):
        subprocess.call(cmd, stdout=subprocess.PIPE, bufsize=1024, universal_newlines=True)



    # Function to kill every program
    async def kill_all(self):
        cmd = ['pkill', '-9', '-f']
        cmd_py = cmd + ['"python "']
        self.call_subprocess(cmd_py)
        cmd_gz = cmd + ['gz']
        self.call_subprocess(cmd_gz)
        cmd_launch = cmd + ['launch.py']
        self.call_subprocess(cmd_launch)
        cmd_exercise = cmd + ['exercise.py']
        self.call_subprocess(cmd_exercise)
        cmd_gui = cmd + ['gui.py']
        self.call_subprocess(cmd_gui)
        try:
            cmd_exercise_guest = cmd + ['exercise_guest.py']
            self.call_subprocess(cmd_exercise_guest)
            cmd_gui_guest = cmd + ['gui_guest.py']
            self.call_subprocess(cmd_gui_guest)
        except:
            pass
        cmd_host = cmd + ['node']
        self.call_subprocess(cmd_host)
        cmd_rosmaster = cmd + ['rosmaster']
        self.call_subprocess(cmd_rosmaster)
        cmd_host = cmd + ['gzserver']
        self.call_subprocess(cmd_host)
        cmd_client = cmd + ['gzclient']
        self.call_subprocess(cmd_client)
        cmd_ros = cmd + ['roslaunch']
        self.call_subprocess(cmd_ros)
        cmd_rosout = cmd + ['rosout']
        self.call_subprocess(cmd_rosout)
        cmd_mel = cmd + ['melodroot']
        self.call_subprocess(cmd_mel)
        cmd_websockify = cmd + ['websockify']
        self.call_subprocess(cmd_websockify)
        cmd_novnc = cmd + ['launch.sh']
        self.call_subprocess(cmd_novnc)
        cmd_console = cmd + ['xterm']
        self.call_subprocess(cmd_console)
        cmd_noetic = cmd + ['noetic']
        self.call_subprocess(cmd_noetic)
        cmd_px4 = cmd + ['px4']
        self.call_subprocess(cmd_px4)


# Main Manager class
class Manager:
    # Initialization function
    def __init__(self):
        self.server = None
        self.client = None
        self.host = "0.0.0.0"
        self.commands = Commands()
        self.launch_level = 0

        self.exercise = None
        self.simulator = None
        self.height = None
        self.width = None

    # Function to handle all the requests
    async def handle(self, websocket, path):
        self.client = websocket

        async for message in websocket:
            data = json.loads(message)
            command = data["command"]

            if command == "open":
                await self.kill_simulation()
                self.width = data.get("width", 1920)
                self.height = data.get("height", 1080)
                self.exercise = data["exercise"]
                if (self.exercise == "laser_mapping"):
                    self.simulator = "stdr"
                elif (self.exercise == "color_filter" or self.exercise == "human detection" or self.exercise == "digit_classifier"):
                    self.simulator = "none"
                else:
                    self.simulator = "gazebo"
            
                try:
                    circuit = data["circuit"]
                    print('CIRCUIT: ')
                    print(circuit)
                except KeyError:
                    circuit = "default"
                
                if not (ACCELERATION_ENABLED):
                    self.open_simulation(self.exercise, self.width, self.height, circuit)
                else:
                    self.open_accelerated_simulation(self.exercise, self.width, self.height, circuit)
            elif command == "resume":
                self.resume_simulation()
                await websocket.send("PingDone{}".format(self.launch_level))
            elif command == "stop":
                self.stop_simulation()
                await websocket.send("PingDone{}".format(self.launch_level))
            elif command == "evaluate":
                await websocket.send("evaluate{}".format(self.evaluate_code(data["code"])))
            elif command == "start":
                self.start_simulation()
            elif command == "reset":
                self.reset_simulation()
                await websocket.send("PingDone{}".format(self.launch_level))
            elif command == "stopgz":
                self.stop_gz()
                await websocket.send("Ping{}".format(self.launch_level))
            elif command == "startgz":
                self.start_gz()
                await websocket.send("Ping{}".format(self.launch_level))
            elif "Pong" in command:
                await websocket.send("Ping{}".format(self.launch_level))
            else:
                await self.kill_simulation()

    # Function to open non-accelerated simulation
    def open_simulation(self, exercise, width, height, circuit):
        print("> Starting simulation")

        # X Server for Console and Gazebo
        self.commands.start_xserver(":0")
        self.commands.start_xserver(":1")

        # Start the exercise
        if exercise not in ["color_filter", "dl_digit_classifier", "human_detection", "laser_mapping"]:
            self.commands.start_gzserver(exercise, circuit)
            self.commands.start_exercise(exercise, circuit=circuit)
            time.sleep(5)
            self.launch_level = 3

            # Start x11vnc servers
            self.commands.start_vnc(":0", 5900, 6080)
            self.commands.start_vnc(":1", 5901, 1108)

            # Start gazebo client
            time.sleep(2)
            self.commands.start_console(width, height)
        elif ("laser_mapping" in exercise):
            self.commands.start_stdrserver(exercise)
            self.commands.start_exercise(exercise)
            time.sleep(5)
            self.launch_level = 3

            # Start x11vnc servers
            self.commands.start_vnc(":0", 5900, 6080)
            self.commands.start_vnc(":1", 5901, 1108)

            self.commands.start_console(1920, 1080)
        else:
            self.commands.start_exercise(exercise)
            time.sleep(2)
            self.launch_level = 3
            self.commands.start_vnc(":1", 5900, 1108)
            self.commands.start_console(1920, 1080)

    # Function to open accelerated simulation
    def open_accelerated_simulation(self, exercise, width, height, circuit):
        print("> Starting accelerated simulation")

        # Stop existing VNC and any accelerated displays
        self.commands.stop_vnc()
        time.sleep(2)

        # Start new VNC and accelerated displays
        self.commands.start_vnc(":0", 5900, 6080)

        # Start the exercise
        if exercise not in ["color_filter", "dl_digit_classifier", "human_detection", "laser_mapping"]:
            self.commands.start_gzserver(exercise, circuit)
            self.commands.start_exercise(exercise, circuit=circuit)
            time.sleep(5)
            self.launch_level = 3

            self.commands.start_vnc(":1", 5901, 1108)

            # Start gazebo client
            time.sleep(2)
            self.commands.start_console(width, height)
        elif ("laser_mapping" in exercise):
            self.commands.start_stdrserver(exercise)
            self.commands.start_exercise(exercise)
            time.sleep(5)
            self.launch_level = 3

            # Start x11vnc servers
            self.commands.start_vnc(":0", 5900, 6080)
            self.commands.start_vnc(":1", 5901, 1108)

            self.commands.start_console(1920, 1080)
        else:
            self.commands.start_exercise(exercise)
            time.sleep(2)
            self.launch_level = 3
            self.commands.start_vnc(":1", 5900, 1108)
            self.commands.start_console(1920, 1080)

    # Function to resume simulation
    def resume_simulation(self):
        print("Resume Simulation")
        self.commands.unpause_physics()

    # Function to stop simulation
    def stop_simulation(self):
        print("Stop Simulation")
        self.commands.pause_physics()

    # Function to start simulation
    def start_simulation(self):
        print("Starting Simulation")
        self.commands.unpause_physics()

    # Function to reset simulation
    def reset_simulation(self):
        print("Reset Simulation")
        self.commands.pause_physics()
        self.commands.reset_physics(self.simulator)

    # Function to start gz client
    def start_gz(self):
        print("Starting Gzclient")
        self.commands.start_gzclient(self.exercise, self.width, self.height)

    # Function to stop gz client
    def stop_gz(self):
        print("Closing Gzclient")
        self.commands.stop_gzclient()

    # Function to kill simulation
    async def kill_simulation(self):
        print("Kill simulation")
        await self.commands.kill_all()
    
    def evaluate_code(self, code):
        try:
            code = re.sub(r'from HAL import HAL', 'from hal import HAL', code)
            code = re.sub(r'from GUI import GUI', 'from gui import GUI', code)
            
            # Avoids EOF error when iterative code is empty (which prevents other errors from showing)
            while_position = re.search(r'[^ ]while\s*\(\s*True\s*\)\s*:|[^ ]while\s*True\s*:|[^ ]while\s*1\s*:|[^ ]while\s*\(\s*1\s*\)\s*:', code)
            sequential_code = code[:while_position.start()]
            iterative_code = code[while_position.start():]
            iterative_code = re.sub(r'[^ ]while\s*\(\s*True\s*\)\s*:|[^ ]while\s*True\s*:|[^ ]while\s*1\s*:|[^ ]while\s*\(\s*1\s*\)\s*:', '\n', iterative_code, 1)
            iterative_code = re.sub(r'^[ ]{4}', '', iterative_code, flags=re.M)
            code = sequential_code + iterative_code

            f = open("user_code.py", "w")
            f.write(code[6:])
            f.close()

            # If the exercise is part of the follow_line challenge then set the path for this challenge
            if self.exercise in CIRCUIT_EX:
                self.exercise = 'follow_line'

            command = "export PYTHONPATH=$PYTHONPATH:/RoboticsAcademy/exercises/static/exercises/{}/web-template; python3 pylint_checker.py".format(self.exercise)
            print('COMANDO: ', command)
            ret = subprocess.run(command, capture_output=True, shell=True)
            result = ret.stdout.decode()
            result = result + "\n"

            # Removes convention and warning messages
            convention_messages = re.search(":[0-9]+: convention.*\n", result)
            while (convention_messages != None):
                result = result[:convention_messages.start()] + result[convention_messages.end():]
                convention_messages = re.search(":[0-9]+: convention.*\n", result)
            warning_messages = re.search(":[0-9]+: warning.*\n", result)
            while (warning_messages != None):
                result = result[:warning_messages.start()] + result[warning_messages.end():]
                warning_messages = re.search(":[0-9]+: warning.*\n", result)

            # Removes unexpected EOF error
            eof_exception = re.search(":[0-9]+: error.*EOF.*\n", result)
            if (eof_exception != None):
                result = result[:eof_exception.start()] + result[eof_exception.end():]

            # Removes no value for argument 'self' error
            self_exception = re.search(":[0-9]+:.*value.*argument.*unbound.*method.*\n", result)
            while (self_exception != None):
                result = result[:self_exception.start()] + result[self_exception.end():]    
                self_exception = re.search(":[0-9]+:.*value.*argument.*unbound.*method.*\n", result)

            # Removes assignment from no return error
            self_exception = re.search(":[0-9]+:.*E1111.*\n", result)
            while (self_exception != None):
                result = result[:self_exception.start()] + result[self_exception.end():]    
                self_exception = re.search(":[0-9]+:.*E1111.*\n", result)

            # Removes E1136 until issue https://github.com/PyCQA/pylint/issues/1498 is closed
            self_exception = re.search(":[0-9]+:.*E1136.*\n", result)
            while (self_exception != None):
                result = result[:self_exception.start()] + result[self_exception.end():]    
                self_exception = re.search(":[0-9]+:.*E1136.*\n", result)

            # Returns an empty string if there are no errors
            error = re.search("error", result)
            if (error == None):
                return ""
            else:
                return result
        except Exception as ex:
            print(ex)

    # Function to start the websocket server
    def run_server(self):
        self.server = websockets.serve(self.handle, self.host, 8765)
        asyncio.get_event_loop().run_until_complete(self.server)
        asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    server = Manager()
    server.run_server()
