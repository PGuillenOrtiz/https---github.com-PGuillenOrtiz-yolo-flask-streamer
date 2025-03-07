from plc import PLCClient

class PLCClientWrapper:
    def __init__(self, ip, rack, slot, db, byte, bit):
        self.client = PLCClient(ip, rack, slot, db, byte, bit)
        self.connect()

    def connect(self):
        try:
            self.client.connect()
        except Exception as e:
            print(f"Error connecting to PLC: {e}")
            self.client = None

    def write_bit(self, value):
        if self.client is not None:
            try:
                self.client.write_bit(value)
            except Exception as e:
                print(f"Error writing to PLC: {e}")

    def close(self):
        if self.client is not None:
            self.client.close()