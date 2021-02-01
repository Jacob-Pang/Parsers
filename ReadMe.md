# ParseRunEvent

Parse-Runner for pushing function calls to and from CMD.
-   Separate arguments are joined with comma-char before
      parsing is executed. Except before the respective exit
      sequences, commas can interfere with the parsability:
-   Spaces after delimiters and operators are not compulsory 
      and are removed during parsing runtime.
-   Typehints (optional) are supported for some subevents and
      do not overwrite other nested typehints.
-   Enclose text in backtick chars (`) to protected the text 
      from parsing, where illegal characters are contained.
-   Collection-type and Function events are chainable as per
      normal method / construction calls:
    ```
        f(g(x))         = <run: f> <run g:> x </run> </run>
        [f(x)]          = [<run: f> x </run>]
        {f(x): g(x)}    = {<run: f> x </run>: <run: g> x </run>}
        ... etc.
    ```

## Parser Synatx for creating Events

function:
  ```
  <run: module.function> arg, -kw=arg, ... </run>
  ```

  the module must be importable, that is, calling the code 
  import module should not raise errors, either:
  -   the module path is in the systme environment variables
  -   the entire module path is specified
  -   the module is in the same directory as Events.py

list:
  ```
  [arg -> type, ...] -> type
  [[arg, ...] -> type, [arg, ...]] -> type
  ```

  elements should NOT be separated into CMD arguments due to 
    additional commas being appended, causing ambiguity on whether 
    to append an empty element.
  typehints are broadcasted in nested lists.

maps (dict):
  ```    
  {kw -> type: arg -> type, ...} -> (type, type)
  ```
  elements should NOT be separated into CMD arguments due
  to additional commas being appended (possible parse-failure)

primitives:
  ```
  var -> type
  ```

## Calling Through Events

To parse-run a function from another module through Events, call
Events with the appropriate argument syntax:

  ### foo.py
  ```
  def foo (x):
      print(x + 1)
  ```
  ### execution from command line
  ```
  cwd. python ParseRunEvent.py "<run: foo.foo> 1 -> int </run>"
  // prints 2
  ```

## Integration into other modules

To integrate the parse-runnability from command line into a
function in another module, decorate the function with the
@parsable_from_cmd decorator:

  ### foo.py 
  ```
  from ParseRunEvent import parsable_from_cmd

  @parsable_from_cmd
  def foo (x):
      print(x + 1)
  ```

  ### execution from command line
  ```
  cwd. python -c "import foo; foo.foo()" "1 -> int"
  // prints 2
  ```