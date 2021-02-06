# ParseRunEvent
CMD-argument Parser for running python scripts and functions.
-   MainProcess class represents the main event of the script
    that encompasses and runs the nested subevents.
-   Event PARAMETERS (settings) refer to modes of running the
    event such as the multiprocess setting in ListEvent.
-   Event ARGUMENTS refer to the members used in constructing
    the event upon running.

## Important Notes:
-   Setting PARAMETERS for the MainProcess must be passed as
      separate arguments on CMD. PARAMETERS are default FALSE
      and declaration sets the PARAMETERS to TRUE state.
-   Separating of event ARGUMENTS into multiple CMD arguments
      should be avoided as these arguments (where not specified
      as PARAMETERS) are joined with a comma before parsing
      is performed and can therefore affect parsability.
-   Spaces after delimiters and operators are not compulsory 
      and are removed during parsing.
-   TYPEHINTS are supported for certain subevents but do not
      overwrite other nested TYPEHINTS. COLLECTION-TYPE events
      support broadcasting of TYPEHINTS.
-   In order to protect a block of text containing illegal chars
      from parsing, enclose the block with backticks (`)
-   COLLECTION-TYPE and FUNCTION-TYPE events support chaining:
    ```
    f(g(x))         = <run: f> <run g:> x </run> </run>
    [f(x), g(x)]    = [<run: f> x </run>, <run: g> x </run>]
    {f(x): g(x)}    = {<run: f> x </run>: <run: g> x </run>}
    f(x), g(x)      = <run: f> x </run> <run g:> x </run>
    ... etc.
    ```

## Subevent Synatx
Functions:
  ```
  <run: module.function> arg, -kw=arg, ... </run>
  ```
  the module must be importable, that is, calling the code 
  import module should not raise errors, either:
  -   the module path is in the systme environment variables
  -   the entire module path is specified
  -   the module is in the same directory as Events.py

Lists:
  ```
  [--multiprocess, arg -> type, ...] -> type
  [[arg, ...] -> type, [arg, ...]] -> type
  ```
  -   TYPEHINTS are broadcasted across nested events
  -   supports MULTIPROCESSING of running subevents with exceptions of
      functions decorated with @pardable_from_cmd (cannot be pickled).

Maps / Dictionaries:
  ```    
  {kw -> type: arg -> type, ...} -> (type, type)
  ```
  -   TYPEHINTS are broadcasted across nested events

Primitive Types:
  ```
  var -> type
  ```

## MainProcess Syntax and Use of ParseRunEvent
MainProcess
-   Functions can be parsed and run either directly through ParseRunEvent
      main or through a @parsable_from_cmd decorator.
-   Parsing of arguments only triggers when the decorated function is
      called from CMD: @parsable_from_cmd does not interfere when the 
      decorated function is called from another python function.
  ```
  // Running a Function from CMD
  // (1) through parsable_from_cmd decorator
  python -c "import module; module.function()"  "--PARAMETERS" "ARGUMENT_SYNTAX"

  // (2) through ParseRunEvent main
  python ParseRunEvent.py "--PARAMETERS" "<run: module.function> ARGUMENT_SYNTAX </run>"

  // Running an Event from CMD
  python ParseRunEvent.py "--PARAMETERS" "SUBEVENT_SYNTAX"
  ```
  
  PARAMETERS
  -   parse_trace:
        trace the steps during the parsing of arguments
  -   run_trace (NOT IMPLEMENTED):
        trace the steps during running of the MainProcess and subevents.
  -   multiprocess:
        use of multiprocessing to run IMMEDIATE subevents: MainProcess extends 
        the ListEvent class, and behaves in the same manner during running.
  -   spawn_subprocess:
        spawns a subprocess to perform the parsing and execution of the MainProcess.
        On runtime error, the script is paused in a definite VISIBLE environment:
        where subprocess_newconsole is TRUE, the PAUSE occurs on the new console,
        otherwise MainProcess RESPAWNS a new VISIBLE console upon error:
        ```
        // LOGIC FLOW (EMBEDDED SUBPROCESS):
        CMD (VISBLE / HIDDEN) -> ParseRunEvent (NO EXECUTION) -> SUBPROCESS (VISBLE / HIDDEN)
                                                                            |
                        EXIT 0 <- NO ERROR <- + ParseRunEvent (EXECUTION) <-
                                                |
                SUBPROCESS (VISIBLE) <- ERROR <-
                        |
                        -> ParseRunEvent (EXECUTION) -> ERROR -> PAUSE -> EXIT 1

        // LOGIC FLOW (SUBPROCESS IN NEW CONSOLE):
        CMD (VISBLE / HIDDEN) -> ParseRunEvent (NO EXECUTION) -> SUBPROCESS (VISBLE)
                                                                        |
                    EXIT 0 <- NO ERROR <- + ParseRunEvent (EXECUTION) <-
                                            |
                EXIT 1 <- PAUSE <- ERROR <-
        ```
        (what's the use?)
        Occurrence of errors cannot be debugged during processes called through a
        hidden console, and lead to immediate termination of the script. The feature
        enables users to identify the errors and control termination of the script.
  -   subprocess_newconsole:
        Specifies that the subprocess is spawned in a new VISIBLE console (forced
        visibility of code execution)

### ParseRunEvent Use Examples
  #### foo.py
  ```
  from ParseRunEvent import parsable_from_cmd

  @parsable_from_cmd
  def foo (x):
      print(x + 1)
  ```
  #### CMD execution
  ```
  cwd. python ParseRunEvent.py "<run: foo.foo> 1 -> int </run>"
  cwd. python -c "import foo; foo.foo()" "1 -> int"
  // prints 2 (exits 0)

  cwd. python ParseRunEvent.py "--parse_trace" "<run: foo.foo> 1 -> int </run>"
  cwd. python -c "import foo; foo.foo()" "--parse_trace" "1 -> int"
  // prints parsing process then 2 (exits 0)

  cwd. python -c "import foo; foo.foo()" "[]"
  // error (exits 1)

  cwd. python -c "import foo; foo.foo()" "--spawn_subprocess" "[]"
  // performs parse-execution in a subprocess, respawns a visible new 
  // separate console to re-perform parse-execution and pauses (exits 1)

  cwd. python -c "import foo; foo.foo()" "--spawn_subprocess" 
  ^ "--subprocess_newconsole" "[]"
  // performs parse-execution in a subprocess in a visible separate console
  // and pauses (exits 1)
  ```