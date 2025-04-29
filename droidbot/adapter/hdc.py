# This is the interface for hdc
import subprocess
import logging
import json
from .adapter import Adapter
from datetime import datetime
import os
import pathlib
from typing import Dict
from ..utils import get_yml_config
from .hmdriver import HmClient
try:
    from shlex import quote # Python 3
except ImportError:
    from pipes import quote # Python 2


config_dir = get_yml_config()

if config_dir["env"].lower() in ["mac", "macos", "linux", "unix"]:
    SYSTEM = "Linux"
elif config_dir["env"].lower() in ["win", "windows"]:
    SYSTEM = "windows"
else:
    raise f"No support for system {config_dir['env']}"

if SYSTEM == "windows":
    HDC_EXEC = "hdc.exe"
elif SYSTEM == "Linux":
    HDC_EXEC = "hdc"


class HDCException(Exception):
    """
    Exception in HDC connection
    """
    pass

class HDC(Adapter):
    """
    interface of HDC
    """
    global HDC_EXEC
    # * HDC command for device info. See the doc below.
    # * https://github.com/codematrixer/awesome-hdc?tab=readme-ov-file#%E6%9F%A5%E7%9C%8B%E8%AE%BE%E5%A4%87%E4%BF%A1%E6%81%AF
    UP = 0
    DOWN = 1
    DOWN_AND_UP = 2
    MODEL_PROPERTY = "const.product.model"
    DEVICE_PROPERTY = "const.product.name"
    VERSION_OS_PROPERTY = "const.product.software.version"
    CPU_STRUCTER_PROPERTY = "const.product.cpu.abilist"
    # VERSION_SDK_PROPERTY = ''
    # VERSION_RELEASE_PROPERTY = ''

    def __init__(self, device=None):
        """
        initiate a HDC connection from serial no
        the serial no should be in output of `hdc devices`
        :param device: instance of Device
        :return:
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        if device is None:
            from droidbot.device import Device
            device = Device()
        self.device = device

        self.cmd_prefix = [HDC_EXEC, "-t", device.serial]

    def set_up(self):
        self.logger.info(f"[CONNECTION] Setting up Adapter hdc.")
        # make the temp path in output dir to store the dumped layout result
        temp_path = os.getcwd() + "/" + self.device.output_dir + "/temp"
        if os.path.exists(temp_path):
            import shutil
            shutil.rmtree(temp_path)
        os.mkdir(temp_path)

    def tear_down(self):
        pass
        # temp_path = os.getcwd() + "/" + self.device.output_dir + "/temp"
        # if os.path.exists(temp_path):
        #     import shutil
        #     shutil.rmtree(temp_path)

    def run_cmd(self, extra_args):
        """
        run a hdc command and return the output
        :return: output of hdc command
        @param extra_args: arguments to run in hdc
        """
        if isinstance(extra_args, str):
            extra_args = extra_args.split()
        if not isinstance(extra_args, list):
            msg = "invalid arguments: %s\nshould be list or str, %s given" % (extra_args, type(extra_args))
            self.logger.warning(msg)
            raise HDCException(msg)

        # args = [HDC_EXEC]
        args = [] + self.cmd_prefix
        args += extra_args

        self.logger.debug('Runing command:')
        self.logger.debug(" ".join([str(arg) for arg in args]))
        r = subprocess.check_output(args).strip()
        if not isinstance(r, str):
            r = r.decode()
        self.logger.debug('Return value:')
        self.logger.debug(r)
        return r

    def shell(self, extra_args):
        """
        run an `hdc shell` command
        @param extra_args:
        @return: output of hdc shell command
        """

        if isinstance(extra_args, str):
            extra_args = extra_args.split()
        if not isinstance(extra_args, list):
            msg = "invalid arguments: %s\nshould be list or str, %s given" % (extra_args, type(extra_args))
            self.logger.warning(msg)
            raise HDCException(msg)

        shell_extra_args = ['shell'] + [ quote(arg) for arg in extra_args ]

        try:
            return self.run_cmd(shell_extra_args)
        except FileNotFoundError as e:
            raise HDCException(f"""{HDC_EXEC} command not found. You're running HMDroidbot in {SYSTEM} mode. Please checkout the SYSTEM variable or your envirnment""")

    def check_connectivity(self):
        """
        check if hdc is connected
        :return: True for connected
        """
        #TODO not support this method
        r = self.run_cmd("list targets")
        return not r.startswith("[Empty]")

    def connect(self):
        """
        connect hdc
        """
        self.logger.debug("connected")

    def disconnect(self):
        """
        disconnect hdc
        """
        self.logger.info("[CONNECTION] %s is disconnected" % self.__class__.__name__)

    def get_property(self, property_name):
        """
        get the value of property
        @param property_name:
        @return:
        """
        return self.shell(["param", "get", property_name])

    def get_model_number(self):
        """
        Get device model number. e.g. SM-G935F
        """
        return self.get_property(HDC.MODEL_PROPERTY)

    def get_sdk_version(self):
        """
        Get version of SDK
        """
        raise NotImplementedError
        return int(self.get_property(HDC.VERSION_SDK_PROPERTY))
    
    def get_device_name(self):
        """
        Get the device Name
        """
        return self.get_property(HDC.DEVICE_PROPERTY)

    def get_release_version(self):
        """
        Get release version, e.g. 4.3, 6.0
        """
        raise NotImplementedError
        return self.get_property(HDC.VERSION_RELEASE_PROPERTY)

    def get_installed_apps(self):
        """
        Get the package names and apk paths of installed apps on the device
        :return: a dict, each key is a package name of an app and each value is the file path to the apk
        """
        app_lines = self.shell("bm dump -a").splitlines()
        installed_bundle = []
        for app_line in app_lines:
            installed_bundle.append(app_line.strip())
        return installed_bundle

    def get_display_density(self):
        display_info = self.get_display_info()
        if 'density' in display_info:
            return display_info['density']
        else:
            return -1.0

    def __transform_point_by_orientation(self, xy, orientation_orig, orientation_dest):
        (x, y) = xy
        if orientation_orig != orientation_dest:
            if orientation_dest == 1:
                _x = x
                x = self.get_display_info()['width'] - y
                y = _x
            elif orientation_dest == 3:
                _x = x
                x = y
                y = self.get_display_info()['height'] - _x
        return x, y

    def get_orientation(self):
        """
        ## ! Function not implemented
        #### TODO hdc rotate cmd not found 
        """
        import inspect
        self.logger.debug(f"function:get_orientation not implemented. Called by {inspect.stack()[1].function}")
        return 1

    def unlock(self):
        """
        Unlock the screen of the device
        """
        self.shell("uitest uiInput keyEvent Home")
        self.shell("uitest uiInput keyEvent Back")

    def press(self, key_code):
        """
        Press a key
        """
        self.shell("uitest uiInput keyEvent %s" % key_code)

    def touch(self, x, y, orientation=-1, event_type=DOWN_AND_UP):
        if orientation == -1:
            orientation = self.get_orientation()
        self.shell("uitest uiInput click %d %d" %
                   self.__transform_point_by_orientation((x, y), orientation, self.get_orientation()))

    def long_touch(self, x, y, duration=2000, orientation=-1):
        """
        Long touches at (x, y)
        """
        if orientation == -1:
            orientation = self.get_orientation()
        self.shell("uitest uiInput longClick %d %d" %
                   self.__transform_point_by_orientation((x, y), orientation, self.get_orientation()))

    def drag(self, start_xy, end_xy, orientation=-1):
        """
        Sends drag event n PX (actually it's using C{input swipe} command.
        @param start_xy: starting point in pixel
        @param end_xy: ending point in pixel
        @param orientation: the orientation (-1: undefined)
        """
        (x0, y0) = start_xy
        (x1, y1) = end_xy
        if orientation == -1:
            orientation = self.get_orientation()
        (x0, y0) = self.__transform_point_by_orientation((x0, y0), orientation, self.get_orientation())
        (x1, y1) = self.__transform_point_by_orientation((x1, y1), orientation, self.get_orientation())

        speed = 4000
        self.shell("uitest uiInput swipe %d %d %d %d %d" % (x0, y0, x1, y1, speed))
        
    def type(self, text):
        # hdc shell uitest uiInput inputText 100 100 hello
        if isinstance(text, str):
            escaped = text.replace("%s", "\\%s")
            encoded = escaped.replace(" ", "%s")
        else:
            encoded = str(text)
        # TODO find out which characters can be dangerous, and handle non-English characters
        self.shell("input text %s" % encoded)

    """
    The following function is especially for HarmonyOS NEXT
    """
    @staticmethod
    def safe_dict_get(view_dict, key, default=None):
        value = view_dict[key] if key in view_dict else None
        return value if value is not None else default
    
    @staticmethod
    def get_relative_path(absolute_path:str) -> str:
        """
        return the relative path in win style
        """
        workspace = pathlib.Path(os.getcwd())
        try:
            if SYSTEM == "windows":
                relative_path = pathlib.PureWindowsPath(pathlib.Path(absolute_path).relative_to(workspace))
                return relative_path
            elif SYSTEM == "Linux":
                return pathlib.Path(absolute_path).relative_to(workspace)
        except ValueError:
            # When app path is not the subpath of workspace, return itself.
            return absolute_path
    
    def push_file(self, local_file, remote_dir="/sdcard/"):
        """
        push file/directory to target_dir
        :param local_file: path to file/directory in host machine
        :param remote_dir: path to target directory in device
        :return:
        """
        if not os.path.exists(local_file):
            self.logger.warning("push_file file does not exist: %s" % local_file)
        self.run_cmd(["file send", local_file, remote_dir])

    def pull_file(self, remote_file, local_file):
        r = self.run_cmd(["file", "recv", remote_file, local_file])
        assert not r.startswith("[Fail]"), "Error with receiving file"
        
    def get_views(self, output_dir):
        
        #* ues HmDriverDumper to get views
        dumper = HmDriverDumper(hdc=self)
        #* use uitest dumper to get views
        # dumper = UitestDumper(hdc=self, output_dir=output_dir)
        
        views = dumper.get_views()

        return views

class Dumper:

    def get_views(self):
        raise NotImplementedError
    
    def get_bounds(self, raw_bounds:str):
        # capturing the coordinate of the bounds and return 2-dimensional list
        # e.g.  "[10,20][30,40]" -->  [[10, 20], [30, 40]]
        import re
        size_pattern = r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]"
        match = re.search(size_pattern, raw_bounds)
        if match:
            return [[int(match.group(1)), int(match.group(2))], \
                    [int(match.group(3)), int(match.group(4))]]

    def get_size(self, raw_bounds:str):
        bounds = self.get_bounds(raw_bounds)
        return f"{bounds[1][0]-bounds[0][0]}*{bounds[1][1]-bounds[0][1]}"

    def transfer_node_to_android_style(self, raw_view: Dict):
        """
        process the view and turn it into the android style
        """
        view = dict()
        for key, value in raw_view.items():
            # adapt the attributes into adb form
            if key in ["visible", "checkable", "enabled", "clickable", \
                       "scrollable", "selected", "focused", "checked"]:
                view[key] = True if value in ["True", "true"] else False
                continue
            if key == "longClickable":
                view["long_clickable"] = bool(value.lower() == "true")
                continue
            if key == "bounds":
                view[key] = self.get_bounds(value)
                view["size"] = self.get_size(value)
                continue
            if key == "bundleName":
                view["package"] = value
                continue
            if key == "description":
                view["content_description"] = value
                continue
            if key == "type":
                view["class"] = value
                continue
            if key == "key":
                view["resource_id"] = value
                continue
            view[key] = value

        if view["class"] in {"RichEditor", "TextInput", "TextArea"}:
            view["editable"] = True

        return view
    
    def transfer_views_to_android_style(self, views_raw: Dict):
        """
        bfs the view tree and turn it into the android style
        views list
        ### :param: view path
        """
        from collections import deque
        self._views = []

        self.views_raw = views_raw
        # process the root node
        self.views_raw["attributes"]["parent"] = -1

        # add it into a queue to bfs
        queue = deque([self.views_raw])
        temp_id = 0

        while queue:
            node: Dict = queue.popleft()

            # process the node and add the hierachy info so that Droidbot can
            # recongnize while traversing
            node["attributes"]["temp_id"] = temp_id
            node["attributes"]["child_count"] = len(node["children"])
            node["attributes"]["children"] = list()

            # process the view, turn it into android style and add to view list
            self._views.append(self.transfer_node_to_android_style(node["attributes"]))

            # bfs the tree
            for child in node["children"]:
                child["attributes"]["parent"] = temp_id
                if "bundleName" in node["attributes"]:
                    child["attributes"]["bundleName"] = HDC.safe_dict_get(node["attributes"], "bundleName")
                    assert self.hdc.safe_dict_get(node["attributes"], "pagePath") is not None, "pagePath not exist"
                    child["attributes"]["pagePath"] = self.hdc.safe_dict_get(node["attributes"], "pagePath")
                queue.append(child)

            temp_id += 1

        # get the 'children' attributes
        self.get_view_children()

        return self._views
    
    def get_view_children(self):
        """
        get the 'children' attributes by the 'parent'
        """
        for view in self._views:
            temp_id = HDC.safe_dict_get(view, "parent")
            if temp_id > -1:
                self._views[temp_id]["children"].append(view["temp_id"])
                assert self._views[temp_id]["temp_id"] == temp_id


class UitestDumper(Dumper):
    """
    This class use uitest to dump layout. Which is 25 times slower than Hidumper.
    But uitest dumpLayout can get some useful messages such as key and pagePath.

    core cmd: hdc shell uitest dumpLayout
    """

    _views = None

    def __init__(self, hdc:HDC, output_dir:str):
        self.output_dir = output_dir
        self.hdc = hdc

    def dump_view(self)->str:
        """
        Using uitest to dumpLayout, and return the remote path of the layout file
        :Return: remote path
        """
        r = self.hdc.shell("uitest dumpLayout")
        assert "DumpLayout saved to" in r, "Error when dumping layout"

        remote_path = r.split(":")[-1]

        file_name = os.path.basename(remote_path)
        temp_path = os.path.join(self.output_dir, "temp")
        local_path = os.path.join(os.getcwd(), temp_path, file_name)

        self.hdc.pull_file(remote_path, HDC.get_relative_path(local_path))

        with open(local_path, "r", encoding="utf-8") as f:
            import json
            self.views_raw = json.load(f)
        
        return self.views_raw

    def get_views(self):
        if self._views is None:
            views_raw = self.dump_view()
            return self.transfer_views_to_android_style(views_raw)
        return self._views


class HmDriverDumper(Dumper):
    """
    This class use HMDriver and uitest to dump layout. 
    """
    device: HmClient = None
    _has_started = False

    def __init__(self, hdc: HDC):
        self.hdc = hdc
        if HmDriverDumper.device is None or not HmDriverDumper._has_started:
            HmDriverDumper.device = HmClient(hdc.device.serial)
            HmDriverDumper.device.start()
            HmDriverDumper._has_started = True

    def _request_hierarchy(self):
        request_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        params = {"api": "captureLayout", "args": []}

        msg = {
            "module": "com.ohos.devicetest.hypiumApiHelper",
            "method": "Captures",
            "params": params,
            "request_id": request_id,
        }

        self.device._send_msg(msg)
        buffer_size = 4096 * 1024
        full_msg = bytearray()
        r = None
        while True:
            try:
                relay = self.device.sock.recv(buffer_size)
                full_msg.extend(relay)
                r = json.loads(full_msg)
                break
            except json.JSONDecodeError as NOT_EOF:
                buffer_size *= 2
                continue
            except (TimeoutError, UnicodeDecodeError) as e:
                import traceback
                traceback.print_exception(e)
                break

        return r["result"] if r is not None else None

    def get_views(self):
        view_dict = self._request_hierarchy()
        if view_dict:
            return self.transfer_views_to_android_style(view_dict)
        else:
            raise RuntimeError("Error when getting views")
