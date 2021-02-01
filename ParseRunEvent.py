import os, sys, inspect
from multiprocessing import Pool

class Event: # interface
    def Run (self):
        pass

class ListEvent(list, Event):
    def __init__ (self, *args):
        super(ListEvent, self).__init__(*args)

    def Run (self) -> list:
        return [ (event.Run() if isinstance(event, Event) 
                else event) for event in self ]

class MapEvent (dict, Event):
    def __init__ (self, *args, **kwargs):
        super(MapEvent, self).__init__(*args, **kwargs)

    def Run (self) -> dict:
        return { key.Run() if isinstance(key, Event) else key:
            arg.Run() if isinstance(arg, Event) else arg
            for key, arg in self.items() }

class FunctionEvent (Event):
    def __init__ (self, function):
        super(FunctionEvent, self).__init__()
        self.function = function
        self.args = ListEvent()
        self.kwargs = MapEvent()

    def Run (self):
        return self.function(*self.args.Run(), **self.kwargs.Run())

# namespace
class EventParser:
    anscii_encryption = {
      "(": "%&#40%",    ")": "%&#41%",
      ",": "%&#44%",    "-": "%&#45%",
      ":": "%&#58%",    ">": "%&#62%",
      "[": "%&#91%",    "]": "%&#93%",
      "{": "%&#123%",   "}": "%&#125%"
    }

    astype_map = {
      "str":    lambda char: str(char),
      "int":    lambda num: int(num),
      "float":  lambda num: float(num),
      "bool":   lambda exp: (exp != "False" and exp != "")
    }

    @staticmethod
    def DecryptCommand (command: str) -> str:
        for protected_char, encryption in EventParser.anscii_encryption.items():
            command = command.replace(encryption, protected_char)

        return command

    @staticmethod
    def ParseEventFromCMD (*sysargs, wrapfunction=None) -> Event:
        event_command = ",".join(sysargs)

        # encrypt protected subcommands
        protected_event_command, protected = "", False

        for char in event_command:
            if char == "`":
                protected = not protected
                continue
            
            if protected and char in EventParser.anscii_encryption:
                char = EventParser.anscii_encryption[char]

            protected_event_command += char

        if not wrapfunction:
            event = ListEvent()
            while protected_event_command:
                subevent, protected_event_command, exit_sequence = EventParser.ParseArgumentFromCMD(
                    protected_event_command, [","])

                event.append(subevent)
        else:
            event, exit_command, exit_sequence = EventParser.ParseFunction(
                    event_command, [","], wrapfunction)

        return event

    @staticmethod
    def ParseArgumentFromCMD (event_command: str, exit_sequences: list = [","]):
        if event_command[0:5] == "<run:":
            return EventParser.ParseFunction(event_command, exit_sequences)

        if event_command[0] == "[":
            return EventParser.ParseList(event_command, exit_sequences)

        if event_command[0] == "{":
            return EventParser.ParseMap(event_command, exit_sequences)

        vararg, event_command, exit_sequence = EventParser.ParseExitSequence(
                event_command, exit_sequences)

        if not "->" in vararg:
            return (EventParser.DecryptCommand(vararg), event_command,
                    exit_sequence)

        vararg = vararg.split("->")
        vararg, type_hint = vararg[0].strip(), vararg[1].strip()
        return EventParser.ParseTypeHint(EventParser.DecryptCommand(vararg),
                type_hint), event_command, exit_sequence

    @staticmethod
    def ParseTypeHint (vararg, type_hint: str):
        astype = lambda arg, type_hint: EventParser.astype_map[type_hint](
                arg) if isinstance(arg, str) else arg

        if isinstance(vararg, dict): # nested dict not supported
            type_hint = type_hint[1::].split(",")
            return { EventParser.ParseTypeHint(kw, type_hint[0].strip()): 
                    EventParser.ParseTypeHint(arg, type_hint[1].strip()) 
                    for kw, arg in vararg.items() }

        if isinstance(vararg, list):
            # supports broadcasting
            return [ EventParser.ParseTypeHint(arg, type_hint) for arg in vararg ]

        return astype(vararg, type_hint)

    @staticmethod
    def ParseExitSequence (event_command: str, exit_sequences: list) -> (str, str, str):
        coerce_end = lambda event_command, index: (len(event_command) if
                index < 0 else index)

        exit_indices = [ coerce_end(event_command, event_command.find(
                exit_sequence)) for exit_sequence in exit_sequences ]

        min_index = min(exit_indices)
        exit_sequence = (exit_sequences[exit_indices.index(min_index)] if 
                min_index < len(event_command) else None)

        return (event_command[0:min_index].strip(), event_command[min_index + 
                (len(exit_sequence) if exit_sequence else 0)::].strip(), 
                exit_sequence)

    @staticmethod
    def RemoveExitSequence (event_command: str, exit_sequences: list) -> (str, str):
        if not len(event_command) or event_command[0] not in exit_sequences:
            return event_command.strip(), None

        exit_sequence = exit_sequences[exit_sequences.index(event_command[0])]
        return event_command[len(exit_sequence)::].strip(), exit_sequence

    @staticmethod
    def ParseFunction (event_command: str, exit_sequences: list = [","],
            function=None) -> (FunctionEvent, str, str):
 
        if not function:
            assert event_command[0:5] == "<run:"
            function = FunctionEvent(None)
            declaration = event_command[5:event_command.find(">")].strip()

            if "." not in declaration:
                function.function = getattr(sys.modules[__name__], declaration)
            else:
                declaration = declaration.split(".")
                function.function = __import__(declaration[0].strip())

                for member in declaration[1::]:
                    function.function = getattr(function.function, member)
                    
            event_command, exit_sequence = EventParser.RemoveExitSequence(
                    event_command[(event_command.find(">") + 1)::], [","])
        else:
            function = FunctionEvent(function)

        while event_command:
            if event_command[0:6] == "</run>":
                event_command = event_command[6::].strip()
                break

            if event_command[0] == "-":
                subcommand = event_command.find("=")
                (function.kwargs[event_command[1:subcommand].strip()], event_command, 
                        exit_sequence) = EventParser.ParseArgumentFromCMD(
                        event_command[(subcommand + 1)::].strip(), [",", "</run>"])
            else:
                arg, event_command, exit_sequence = EventParser.ParseArgumentFromCMD(
                        event_command, [",", "</run>"])

                function.args.append(arg)

            if exit_sequence == "</run>": break

        return (function, *EventParser.RemoveExitSequence(event_command, 
                exit_sequences))

    @staticmethod
    def ParseList (event_command: str, exit_sequences: list = [","]):
        assert event_command[0] == "["
        event_command, arglist = event_command[1::].strip(), ListEvent()

        while event_command:
            if event_command[0] == "]":
                event_command = event_command[1::].strip()
                break

            vararg, event_command, exit_sequence = EventParser.ParseArgumentFromCMD(
                    event_command, [",", "]"])
            
            arglist.append(vararg)
            if exit_sequence == "]": break
        
        if event_command[0:2] == "->":
            type_hint, event_command, exit_sequence = EventParser.ParseExitSequence(
                    event_command[2::], exit_sequences)

            return (EventParser.ParseTypeHint(arglist, type_hint), event_command,
                    exit_sequence)

        return (arglist, *EventParser.RemoveExitSequence(event_command,
                exit_sequences))
    
    @staticmethod
    def ParseMap (event_command: str, exit_sequences: list = [","]):
        assert event_command[0] == "{"
        event_command, argmap = event_command[1::].strip(), MapEvent()

        while event_command:
            if event_command[0] == "}":
                event_command = event_command[1::].strip()
                break

            varkey, event_command, exit_sequence = EventParser.ParseArgumentFromCMD(
                    event_command, [":"])

            vararg, event_command, exit_sequence = EventParser.ParseArgumentFromCMD(
                    event_command, [",", "}"])
            
            argmap[varkey] = vararg
            if exit_sequence == "}": break

        if event_command[0:2] == "->":
            type_hint, event_command, exit_sequence = EventParser.ParseExitSequence(
                    event_command[2::], ")")
            argmap = EventParser.ParseTypeHint(argmap, type_hint)

        return (argmap, *EventParser.RemoveExitSequence(event_command,
                exit_sequences))

# function decorator
def parsable_from_cmd (function):
    def wrapped_function(*args, **kwargs):
        if inspect.stack()[1][3] != "<module>": 
            return function(*args, **kwargs)

        return EventParser.ParseEventFromCMD(*sys.argv[1::], 
                wrapfunction=function).Run()

    return wrapped_function

if __name__ == "__main__":
    sys.exit(EventParser.ParseEventFromCMD(*sys.argv[1::])[0].Run())