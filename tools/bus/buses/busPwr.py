import yaml


def readBus():
    try:
        with open('/home/tim-drake/Git/Hybrid/tools/bus/buses/busPwr.yaml', 'r') as file:
            # Use yaml.safe_load() for security, especially with untrusted sources
            data = yaml.safe_load(file)
        

        return data

    except FileNotFoundError:
        print("Error: file not found. Please ensure the file exists.")
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")


if __name__ == "__main__":
    bus = readBus()
    print(bus)
    print(f"Bus: {bus['name']}")