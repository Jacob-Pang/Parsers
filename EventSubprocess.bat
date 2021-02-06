@ECHO OFF

@ECHO _____________________________________________________________________________________________
@ECHO *********************************************************************************************
@ECHO EventSubprocess spawned by ParseRunEvent:
@ECHO --------------------------------------------
@ECHO version.21_02_06
@ECHO _____________________________________________________________________________________________
@ECHO *********************************************************************************************

SET pythonexe=%1
SET eventcommand=%2
SET errorevent=%3

SET eventargs=""
:LOOP
IF [%4]==[] GOTO AFTERLOOP
SET eventargs=%eventargs% %4
SHIFT
GOTO LOOP
:AFTERLOOP

%pythonexe% "ParseRunEvent.py" %eventcommand% %eventargs%
SET returncode=%ERRORLEVEL%

IF %returncode%==0 EXIT %returncode%
IF %errorevent%==RESPAWN (
  @ECHO RESPAWNED Event
  %pythonexe% "ParseRunEvent.py" %eventcommand% "--spawn_subprocess" "--subprocess_newconsole" %eventargs%
) ELSE (
  PAUSE
)

EXIT %returncode%
