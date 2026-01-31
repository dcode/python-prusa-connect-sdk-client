from pydantic_settings import BaseSettings, CliApp, CliSubCommand
from typing import Annotated, Union

class CmdA(BaseSettings):
    name: str = "foo"
    
    def cli_cmd(self):
        print(f"CmdA executed with name={self.name}")

class CmdB(BaseSettings):
    count: int = 1
    
    def cli_cmd(self):
        print(f"CmdB executed with count={self.count}")

class Config(BaseSettings):
    debug: bool = False
    # Use CliSubCommand to define subcommands
    sub_command: Annotated[Union[CmdA, CmdB], CliSubCommand]
    
    model_config = {"cli_parse_args": True}

if __name__ == "__main__":
    import sys
    # simulate args
    print("--- Test CmdA ---")
    CliApp.run(Config, cli_args=["--debug", "true", "cmd-a", "--name", "bar"])
    print("\n--- Test CmdB ---")
    CliApp.run(Config, cli_args=["cmd-b", "--count", "42"])
