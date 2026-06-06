# mhxy-automator

## Overview
The **mhxy-automator** project is an automated bot designed to play the game "梦幻西游" (Dream of the Red Chamber). This bot interacts with the game by simulating user inputs and automating various tasks to enhance gameplay experience.

## Project Structure
```
mhxy-automator
├── src
│   ├── app.py                # Main entry point of the application
│   ├── bot                   # Contains bot-related logic
│   │   ├── __init__.py
│   │   ├── core.py           # Main logic coordinating bot actions
│   │   ├── actions.py        # Defines actions like mouse clicks and screen dragging
│   │   ├── navigation.py      # Handles navigation within the game
│   │   ├── vision.py         # Captures images and locates text coordinates
│   │   └── input_control.py   # Manages input control for simulating actions
│   ├── config                # Configuration settings for the application
│   │   └── settings.py
│   ├── plugins               # Example plugins for extending functionality
│   │   └── example_plugin.py
│   ├── utils                 # Utility functions and classes
│   │   ├── __init__.py
│   │   ├── logger.py         # Logging utilities
│   │   └── scheduler.py      # Task scheduling utilities
│   └── tests                 # Unit tests for the bot
│       └── test_core.py
├── requirements.txt          # Project dependencies
├── pyproject.toml            # Packaging and dependency management
├── setup.cfg                 # Project configuration settings
├── .gitignore                # Files to ignore in version control
└── README.md                 # Project documentation
```

## Installation
To set up the project, clone the repository and install the required dependencies:

```bash
git clone <repository-url>
cd mhxy-automator
pip install -r requirements.txt
```

## Usage
To run the bot, execute the following command:

```bash
python src/app.py
```

Follow the on-screen instructions to select the game window and start the automation process.

## Contributing
Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.