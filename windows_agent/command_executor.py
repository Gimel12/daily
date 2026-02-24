"""
Remote Command Executor — Run commands on the Windows PC remotely.
"""
import subprocess
import logging
import shlex
from typing import Dict

logger = logging.getLogger("command_executor")

# Commands that are never allowed (safety guard)
BLOCKED_COMMANDS = [
    "format",
    "del /s",
    "rd /s",
    "rmdir /s",
    "diskpart",
]


def _is_blocked(command: str) -> bool:
    """Check if a command contains blocked patterns."""
    cmd_lower = command.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return True
    return False


def execute_command(command: str, shell: str = "powershell",
                    timeout: int = 60) -> Dict:
    """
    Execute a command on the Windows PC.

    Args:
        command: The command string to execute.
        shell: "powershell" or "cmd".
        timeout: Max seconds to wait for the command.

    Returns:
        Dict with stdout, stderr, return_code, and success.
    """
    if _is_blocked(command):
        return {
            "stdout": "",
            "stderr": f"Command blocked by safety filter: {command}",
            "return_code": -1,
            "success": False,
        }

    logger.info(f"Executing [{shell}]: {command}")

    try:
        if shell == "powershell":
            full_cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            full_cmd = ["cmd", "/c", command]

        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "success": result.returncode == 0,
        }

        logger.info(f"Command finished with return code {result.returncode}")
        return output

    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out after {timeout}s: {command}")
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "return_code": -1,
            "success": False,
        }
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        return {
            "stdout": "",
            "stderr": str(e),
            "return_code": -1,
            "success": False,
        }
