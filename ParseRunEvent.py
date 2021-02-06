import os, sys, inspect, subprocess
from multiprocessing import Pool

class Event: # interface
    def run (self):
        pass

    def parse_command (self, command: str) -> str:
        pass

    def astype (self):
        pass

    @staticmethod
    def map_type (expected_event, type_hint: str):
        if isinstance(expected_event, Event):
            return expected_event.astype(type_hint)

        if isinstance(expected_event, str):
            return CommandParser.type_map[type_hint](
                    expected_event)

        return expected_event

    @staticmethod
    def run_event (expected_event):
        if isinstance(expected_event, Event):
            return expected_event.run()

        return expected_event


class ListEvent(list, Event):
    def __init__ (self, *args, multiprocess=False):
        super(ListEvent, self).__init__(*args)
        self.multiprocess = multiprocess

    def run (self) -> list:
        if self.multiprocess:
            return Pool(os.cpu_count()).map(Event.run_event, self)
        
        return [ Event.run_event(subevent) for subevent in self ]

    def parse_command (self, command: str, exit_sequences: tuple) -> tuple:
        command = command.strip()
        assert command[0] == "["
        command = command[1::].strip()

        exit_sequence = None
        while command and exit_sequence != "]":
            if command[0] == "]":
                command = command[1::].strip()
                break

            if command[0:2] == "--":
                setting, exit_sequence, command = CommandParser.parse_next(
                        command[2::], (" ", ",", "]"))
                setattr(self, setting, True)
                continue

            # event setting flag
            subevent, exit_sequence, command = CommandParser.parse_next(
                    command, (",", "]"))

            self.append(subevent)
        
        if command[0:2] == "->":
            type_hint, exit_sequence, command = CommandParser.parse_next(
                command[2::], exit_sequences)
            self.astype(type_hint.strip())
        else:
            white_space, exit_sequence, command = CommandParser.parse_next(
                command, exit_sequences)
        
        return self, exit_sequence, command

    def astype (self, type_hint):
        # broadcasting of types
        self = ListEvent([ Event.map_type(subevent, type_hint) for subevent 
                in self ], multiprocess=self.multiprocess)


class MapEvent (dict, Event):
    def __init__ (self, *args, **kwargs):
        super(MapEvent, self).__init__(*args, **kwargs)

    def run (self) -> dict:
        return {
            Event.run_event(key_subevent): Event.run_event(arg_subevent)
            for key_subevent, arg_subevent in self.items()
        }

    def parse_command (self, command: str, exit_sequences: tuple) -> tuple:
        command = command.strip()
        assert command[0] == "{"
        command = command[1::].strip()

        exit_sequence = None
        while command and exit_sequence != "}":
            if command[0] == "}":
                command = command[1::].strip()
                break

            if command[0:2] == "--":
                setting, exit_sequence, command = CommandParser.parse_next(
                        command[2::], (" ", ",", "}"))
                setattr(self, setting, True)
                continue
        
            key_subevent, exit_sequence, command = CommandParser.parse_next(
                    command, (":"))
            arg_subevent, exit_sequence, command = CommandParser.parse_next(
                    command, (",", "}"))
            
            self[key_subevent] = arg_subevent

        if command[0:2] == "->":
            type_hint, exit_sequence, command = CommandParser.parse_next(
                command[2::], exit_sequences)
            self.astype(type_hint.strip())
        else:
            white_space, exit_sequence, command = CommandParser.parse_next(
                command, exit_sequences)
        
        return self, exit_sequence, command

    def astype (self, type_hint):
        # type_hint not compatible with event type map
        if (type_hint[0] != "(" or type_hint[-1] != ")" or 
                "," not in type_hint):
            return

        type_hint = type_hint[1:-1].split(",")
        self =MapEvent(**{
            Event.map_type(key_subevent, type_hint[0].strip()): 
            Event.map_type(arg_subevent, type_hint[1].strip())
            for key_subevent, arg_subevent in self
        })


class FunctionEvent (Event):
    def __init__ (self, function=None):
        super(FunctionEvent, self).__init__()
        self.function = function
        self.args = ListEvent()
        self.kwargs = MapEvent()

    def run (self):
        return self.function(*Event.run_event(self.args), 
                **Event.run_event(self.kwargs))

    def parse_command(self, command: str, exit_sequences: tuple,
            wrapper_function=None) -> tuple:

        if not wrapper_function:
            command = command.strip()
            assert command[0:5] == "<run:"
            function_sequence = command[5:command.find(">")].strip()

            if "." not in function_sequence:
                self.function = getattr(sys.modules[__name__], function_sequence)
            else:
                function_sequence = function_sequence.split(".")
                self.function = __import__(function_sequence[0].strip())

                for member in function_sequence[1::]:
                    self.function = getattr(self.function, member)

            command = command[command.find(">") + 1::].strip()
        else:
            self.function = wrapper_function

        exit_sequence = None
        while command and exit_sequence != "</run>":
            if command[0:6] == "</run>":
                command = command[6::].strip()
                break

            if command[0:2] == "--":
                setting, exit_sequence, command = CommandParser.parse_next(
                        command[2::], (" ", ",", "</run>"))
                setattr(self, setting, True)
                continue

            if command[0] == "-":
                key = command[1:command.find("=")].strip()
                subevent, exit_sequence, command = CommandParser.parse_next(
                        command[command.find("=") + 1::].strip(), (",", "</run>"))

                self.kwargs[key] = subevent
            else:
                subevent, exit_sequence, command = CommandParser.parse_next(
                        command, (",", "</run>"))

                self.args.append(subevent)

        white_space, exit_sequence, command = CommandParser.parse_next(
                command, exit_sequences)

        return self, exit_sequence, command

    def astype (self, type_hint):
        # no type broadcasting allowed
        pass


class MainProcess (ListEvent):
    def __init__ (self, *args, multiprocess=False, spawn_subprocess=False, 
            subprocess_nowindow=False, echo_exitstatus=False):

        super(MainProcess, self).__init__(*args,
                multiprocess=multiprocess)

        self.spawn_subprocess = spawn_subprocess
        self.subprocess_nowindow = subprocess_nowindow
        self.echo_exitstatus = echo_exitstatus

    def spawn_runsubprocess (self, command: str) -> None:
        if self.subprocess_nowindow:
            respawn_onerror, creationflag = "1", subprocess.CREATE_NO_WINDOW
        else:
            respawn_onerror, creationflag = "0", subprocess.CREATE_NEW_CONSOLE

        echo_status = "1" if self.echo_exitstatus else "0"

        spawn = subprocess.Popen([ "EventSubprocess.bat", os.getcwd(), 
                respawn_onerror, sys.executable, command, echo_status ], 
                creationflags=creationflag)

        stdout, stderr = spawn.communicate()
        sys.exit(spawn.returncode)

    def parse_process_params (self, *sysargs) -> tuple:
        commands = []
        for sysarg in sysargs:
            if "--" in sysarg:
                setattr(self, sysarg[2::].strip(), True)
            else:   commands.append(sysarg)
        
        return ",".join(commands)

    @staticmethod
    def parserun_from_cmd (*sysargs) -> None:
        process = MainProcess()
        command = process.parse_process_params(*sysargs)

        if process.spawn_subprocess:
            process.spawn_runsubprocess(command)

        process, exit_sequence, exit_command = process.parse_command(
            CommandParser.encrypt("[" + command + "]"), (","))

        sys.exit(process.run())


class CommandParser:
    encryption_map = {
      "(": "%&#40%",    ")": "%&#41%",
      ",": "%&#44%",    "-": "%&#45%",
      ":": "%&#58%",    ">": "%&#62%",
      "[": "%&#91%",    "]": "%&#93%",
      "{": "%&#123%",   "}": "%&#125%"
    }

    type_map = {
      "str":    lambda char: str(char),
      "int":    lambda num: int(num),
      "float":  lambda num: float(num),
      "bool":   lambda exp: (exp != "False" and exp != "")
    }

    @staticmethod
    def encrypt (command: str) -> str:
        '''
        '''
        encrypted_command, protected = "", False

        for char in command:
            if char == "`":
                protected = not protected
                continue
            
            if protected and char in CommandParser.encryption_map:
                char = CommandParser.encryption_map[char]

            encrypted_command += char

        return encrypted_command

    @staticmethod
    def decrypt (command: str) -> str:
        for protected_char, encrypted_sequence in CommandParser.encryption_map.items():
            command = command.replace(encrypted_sequence, protected_char)

        return command

    @staticmethod
    def parse_next (command: str, exit_sequences: tuple):
        '''
            greedy-recursive algorithm.
            returns
                out: tuple in the sequence of <parsed_event_object> 
                    <exit_sequence> <command_remainder>
        '''
        command = command.strip()
        if not len(command): return "", "", ""

        if command[0:5] == "<run:":
            return FunctionEvent().parse_command(command,
                    exit_sequences)
        
        if command[0:5] == "<try:":
            return FunctionEvent().parse_command(command,
                    exit_sequences)

        if command[0] == "[":
            return ListEvent().parse_command(command,
                    exit_sequences)

        if command[0] == "{":
            return MapEvent().parse_command(command,
                    exit_sequences)

        # var argument ***********************************************
        exit_indices = [ command.find(sequence) for sequence 
                in exit_sequences ]

        mindex = min([ len(command) if exit_index < 0 else exit_index for
                exit_index in exit_indices ])
        
        exit_sequence = (exit_sequences[exit_indices.index(mindex)] if
            mindex != len(command) else "")

        event = CommandParser.decrypt(command[0:mindex].strip())

        if "->" in event:
            event = event.split("->")
            event = CommandParser.type_map[event[1].strip()](
                    event[0].strip())

        return (event, exit_sequence, command[mindex + 
                len(exit_sequence)::].strip())

# function decorator
def parsable_from_cmd (function, spawn_subprocess=False,
        subprocess_nowindow=False):

    def wrapped_function(*args, **kwargs):
        redirected_from = inspect.stack()[1]

        if redirected_from[3] != "<module>": 
            return function(*args, **kwargs)

        process = MainProcess(spawn_process=spawn_subprocess,
                subprocess_nowindow=subprocess_nowindow)
        
        command = process.parse_process_params(*sys.argv[1::])
        if process.spawn_subprocess:
            module = inspect.getmodule(redirected_from[0])
            process.spawn_runsubprocess("<run:" + module.__name__
                    + "." + function.__name__ + ">" + command
                    + "</run>")

        process.append(FunctionEvent().parse_command(
                CommandParser.encrypt(command), function))
        sys.exit(process.run())

    return wrapped_function

if __name__ == "__main__":
    process = MainProcess.parserun_from_cmd(*sys.argv[1::])
    sys.exit(process.Run())