## Development
This project uses a Nix shell to provide a development environment. 
To develop on this plugin, please ensure first that you have [installed the Nix package manager](https://nixos.org/download/), ideally, or that you have all the dependencies you'll need otherwise installed (e.g., in a virtual environment you're managing separately).

By default, with `nix-shell`, you should have all the dependencies you'll need not only to _use_ this plugin, but also to _develop_ on it. 
In other words, dependencies to do things like run tests, run linter(s), and run type checking should all be provided. 
If you try and that's not the case, please check the [Issue Tracker](https://github.com/gerlichlab/looptrace-napari/issues).
If an issue's open for what you're experiencing, please upvote the initial description of the issue and/or comment on the ticket.
