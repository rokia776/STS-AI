# Python Logging 

A simple demonstration of Python's built-in `logging` module, showing all five standard logging levels.

## Project Structurepython_logging_assignment/
├── main.py              # Main script that demonstrates all logging levels
├── logging_config.py    # Central logging configuration
├── application.log      # Generated log file (created after running the script)


| Level     | Description                                      |
|-----------|--------------------------------------------------|
| DEBUG     | Detailed information for diagnosing problems     |
| INFO      | Confirmation that things are working as expected |
| WARNING   | Something unexpected happened, but the app still works |
| ERROR     | A more serious problem, the app couldn't perform some function |
| CRITICAL  | A serious error indicating the program may not be able to continue |

## How to Run

```bash
python main.pyAfter running, check the generated application.log file. You should see entries like:text2026-10-27 15:46:17 | DEBUG | Debug message: checking the application's internal state.
2026-10-27 15:46:17 | INFO | Info message: application started successfully.
2026-10-27 15:46:17 | WARNING | Warning message: configuration value missing; using default.
2026-10-27 15:46:17 | ERROR | Error message: failed to load the optional input file.
2026-10-27 15:46:17 | CRITICAL | Critical message: required service is unavailable.Configuration Details
Log file: application.log
Log level: DEBUG (captures all messages)
Format: YYYY-MM-DD HH:MM:SS | LEVEL | message
Encoding: UTF-8
Fileslogging_config.pyContains the configure_logging() function that sets up the logging system using logging.basicConfig.main.pyCalls the configuration and logs one message for each of the five levels.
