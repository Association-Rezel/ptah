import argparse
import jinja2
from jinja2 import Template
import yaml
import os
from models import *
from pathlib import Path

def main(config_path: Path, dockerfile_template_path: Path, output: Path):

    if not config_path:
        print("Please provide path to configuration file")
        os._exit(1)

    try:
        with open(config_path, "r") as file:
            config_data = yaml.safe_load(file)
        ptah_config = PtahConfig(**config_data)
    except Exception as e:
        print("Error loading configuration file:", e)
        os._exit(1)

    try:
        with open(dockerfile_template_path) as f:
            template = Template(f.read())
            dockerfile_content = template.render(ptah_config=ptah_config)

            with open(output, 'w') as output_f:
                output_f.write(dockerfile_content)
    except Exception as e:
        print("Error loading Dockerfile template:", e)
        os._exit(1)


# --------------------------------- Entry Point --------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ptah Configuration Processor")
    parser.add_argument(
        "--config", required=True, help="Path to Ptah configuration file"
    )
    
    parser.add_argument("--dockerfile-template", help="Path to Dockerfile template")
    parser.add_argument("--dockerfile-output", help="Path to output Dockerfile")
    
    args = parser.parse_args()
    
    if not args.config:
        print("Please provide path to configuration file")
        os._exit(1)
    
    if args.dockerfile_template:
        dockerfile_template = Path(args.dockerfile_template)
    else:
        dockerfile_template = Path('Dockerfile.j2')
        
    if args.dockerfile_output:
        output = Path(args.dockerfile_output)
    else:
        output = Path('Dockerfile')

    main(Path(args.config), dockerfile_template, output)
