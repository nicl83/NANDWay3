#!/usr/bin/python
# *************************************************************************
# Python 3.x rewrite by nicl83
# *************************************************************************
# Teensy++ 2.0 modifications by Effleurage
#  NANDway.py
#
# Teensy++ 2.0 modifications by judges@eEcho.com
# *************************************************************************
#  noralizer.py - NOR flasher for PS3
#
# Copyright (C) 2010-2011  Hector Martin "marcan" <hector@marcansoft.com>
#
# This code is licensed to you under the terms of the GNU GPL, version 2;
# see file COPYING or http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
# *************************************************************************

import time
import datetime
import sys
import serial


class TeensySerialError(Exception):
    "Exception class for errors when communicating with the Teensy."


class TeensySerial:
    "Class for communicating with a Teensy running NANDWay firmware."
    BUFSIZE = 32768

    def __init__(self, port: str):
        try:
            self.ser = serial.Serial(
                port,
                baudrate=9600,
                timeout=300,
                rtscts=False,
                dsrdtr=False,
                xonxoff=False,
                write_timeout=120)
        except serial.SerialException as exc:
            raise TeensySerialError(f"could not open serial {port}") from exc
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.obuf: bytearray = bytearray()

    def write(self, write_data: int | bytes):
        """
        Add data to the output buffer.
        If data overflows buffer, it will be flushed to the device. (FIFO)
        """
        if isinstance(write_data, int):
            self.obuf.append(write_data)
        else:
            self.obuf.extend(write_data)
        while len(self.obuf) > self.BUFSIZE:
            self.ser.write(self.obuf[:self.BUFSIZE])
            self.obuf = self.obuf[self.BUFSIZE:]

    def flush(self):
        "Flush the output buffer to the device."
        if len(self.obuf):
            self.ser.write(self.obuf)
            self.ser.flush()
            self.obuf.clear()

    def read(self, size: int):
        "Read data from the serial device."
        self.flush()
        read_data = self.ser.read(size)
        return read_data

    def readbyte(self):
        "Read one byte from the serial device."
        return self.read(1)[0]

    def close(self):
        "Close the serial device."
        print()
        print("Closing serial device...")
        self.ser.close()
        print("Done.")


class NANDError(Exception):
    "Exception class for errors when interacting with the NAND."


class NANDFlasher(TeensySerial):
    "Class for a NAND flasher using a Teensy running NANDWay firmware."
    # pylint: disable=too-many-instance-attributes
    mf_id: int = 0
    device_id: int = 0
    nand_page_size: int = 0
    nand_ras: int = 0  # Redundent Area Size
    nand_page_size_plus_ras: int = 0
    nand_page_count: int = 0
    nand_block_count: int = 0
    nand_pages_per_block: int = 0
    nand_block_size: int = 0
    nand_block_size_plus_ras: int = 0
    nand_bus_width: int = 0
    nand_plane_count: int = 0
    nand_plane_size: int = 0

    # Teensy commands
    CMD_PING1 = 0
    CMD_PING2 = 1
    CMD_BOOTLOADER = 2
    CMD_IO_LOCK = 3
    CMD_IO_RELEASE = 4
    CMD_PULLUPS_DISABLE = 5
    CMD_PULLUPS_ENABLE = 6
    CMD_NAND0_ID = 7
    CMD_NAND0_READPAGE = 8
    CMD_NAND0_WRITEPAGE = 9
    CMD_NAND0_ERASEBLOCK = 10
    CMD_NAND1_ID = 11
    CMD_NAND1_READPAGE = 12
    CMD_NAND1_WRITEPAGE = 13
    CMD_NAND1_ERASEBLOCK = 14

    # NAND names
    NAND_NAMES = {
        0xEC: {  # Samsung
            "vendor_name": "Samsung",
            0xA1: "K9F1G08R0A",
            0XD5: "K9GAG08U0M",
            0xF1: "K9F1G08U0A",
            0x79: "K9T1G08U0M",
            0xDA: "K9F2G08U0M"
        },
        0xAD: {  # Hynix (oh no)
            "vendor_name": "Hynix",
            0x73: "HY27US08281A",
            0xD7: "H27UBG8T2A",
            0xDA: "HY27UF082G2B",
            0xDC: "H27U4G8F2D"
        },
        0x98: {  # Toshiba
            "vendor_name": "Toshiba",
            0xDC: "TC58NVG2S3E"
        }
    }

    def __init__(self, port: str, nand_id: int, ver_major: int, ver_minor: int):
        if port:
            super().__init__(port)
        self.nand_id = nand_id & 1
        self.nand_disable_pullups = nand_id & 10
        self.version_major = ver_major
        self.version_minor = ver_minor

    def ping(self):
        "Ping the Teensy and check the firmware version."
        self.write(self.CMD_PING1)
        self.write(self.CMD_PING2)
        ver_major = self.readbyte()
        ver_minor = self.readbyte()
        free_ram = (self.readbyte() << 8) | self.readbyte()
        if (ver_major != self.version_major) or (ver_minor != self.version_minor):
            print(
                "Ping failed",
                f"(expected v{self.version_major}.{self.version_minor:02},",
                f"got {ver_major}.{ver_minor:02})"
            )
            self.close()
            sys.exit(1)

        return free_ram

    def readid(self):
        "Read the manufacturer and device IDs from the device."
        if self.nand_disable_pullups == 0:
            self.write(self.CMD_PULLUPS_ENABLE)
        else:
            self.write(self.CMD_PULLUPS_DISABLE)

        if self.nand_id == 1:
            self.write(self.CMD_NAND1_ID)
        else:
            self.write(self.CMD_NAND0_ID)

        is_command_supported = self.readbyte()
        if is_command_supported != 89:  # 'Y'
            print()
            print("NAND_ID 1 not supported for Signal Booster Edition! Exiting...")
            self.close()
            sys.exit(1)

        nand_info = self.read(25)

        print("Raw ID info:",
              ' '.join(f"0x{byte:02x}" for byte in nand_info[0:5])
              )

        self.mf_id = nand_info[0]
        self.device_id = nand_info[1]

        self.nand_page_size = (nand_info[5] << 24) | (
            nand_info[6] << 16) | (nand_info[7] << 8) | nand_info[8]

        self.nand_ras = (nand_info[9] << 8) | nand_info[10]

        self.nand_bus_width = nand_info[11]

        self.nand_block_size = (nand_info[12] << 24) | (
            nand_info[13] << 16) | (nand_info[14] << 8) | nand_info[15]
        self.nand_block_count = (nand_info[16] << 24) | (
            nand_info[17] << 16) | (nand_info[18] << 8) | nand_info[19]

        self.nand_plane_count = nand_info[20]
        self.nand_plane_size = (nand_info[21] << 24) | (
            nand_info[22] << 16) | (nand_info[23] << 8) | nand_info[24]

        if (self.nand_page_size <= 0):
            print()
            print("Error reading size of NAND! Exiting...")
            self.close()
            sys.exit(1)
        if (self.nand_bus_width != 8):
            print()
            print("Only 8-bit NANDs are supported! Exiting...")
            self.close()
            sys.exit(1)
        if (self.mf_id == 0):
            print()
            print("Unknown chip manufacturer! Exiting...")
            self.close()
            sys.exit(1)
        if (self.device_id == 0):
            print()
            print("Unknown device id! Exiting...")
            self.close()
            sys.exit(1)

        if self.mf_id == 0x98 and self.device_id == 0xdc:
            # TC58NVG2S3E
            self.nand_block_count = self.nand_block_count // 4
            self.nand_plane_size = self.nand_plane_size // 4

        self.nand_pages_per_block = int(
            self.nand_block_size / self.nand_page_size)
        self.nand_page_size_plus_ras = self.nand_page_size + self.nand_ras
        self.nand_page_count = self.nand_pages_per_block * self.nand_block_count
        self.nand_block_size_plus_ras = self.nand_pages_per_block * \
            self.nand_page_size_plus_ras

    def printstate(self):
        "Print information on the current NAND state."
        # print "NAND%d information:"%self.NAND_ID
        print(f"NAND{self.nand_id} information:")
        self.readid()

        print()
        if self.mf_id in self.NAND_NAMES:
            mfg_name = self.NAND_NAMES[self.mf_id]['vendor_name']
            nand_name = self.NAND_NAMES[self.mf_id].get(
                self.device_id, "Unknown")
            print(f"NAND chip manufacturer: {mfg_name} (0x{self.mf_id:02x})")
            print(
                f"NAND chip type:        {nand_name} (0x{self.device_id:02x})")
        else:
            print(f"NAND chip manufacturer: unknown (0x{self.mf_id:02x})")
            print(f"NAND chip type:        unknown (0x{self.device_id:02x})")

        print(f"""
        NAND size:              {self.nand_block_size * self.nand_block_count / 1024 / 1024} MB
        NAND plus RAS size:     {self.nand_block_size_plus_ras * self.nand_block_count / 1024 / 1024} MB
        Page size:              {self.nand_page_size} bytes
        Page plus RAS size:     {self.nand_page_size_plus_ras} bytes
        Block size:             {self.nand_block_size} bytes
        Block plus RAS size:    {self.nand_block_size_plus_ras} bytes
        RAS size:               {self.nand_ras} bytes
        Plane size:             {self.nand_plane_size}
        Pages per block:        {self.nand_pages_per_block}
        Number of blocks:       {self.nand_block_count}
        Number of pages:        {self.nand_page_count}
        Number of planes:       {self.nand_plane_count}
        Bus width:              {self.nand_bus_width}-bit
        """)

    def bootloader(self):
        self.write(self.CMD_BOOTLOADER)
        self.flush()

    def read_result(self):
        # read status byte
        res = self.readbyte()

        # 'K' = okay, 'T' = timeout error when writing, 'R' = Teensy receive buffer timeout, 'V' = Verification error
        error_msg = ""

        if (res != 75):  # 'K'
            if (res == 84):  # 'T'
                error_msg = "RY/BY timeout error while writing!"
            elif (res == 82):  # 'R'
                self.close()
                raise NANDError(
                    "Teensy receive buffer timeout! Disconnect and reconnect Teensy!")
            elif (res == 86):  # 'V'
                error_msg = "Verification error!"
            elif (res == 80):  # 'P'
                error_msg = "Device is write-protected!"
            else:
                self.close()
                raise NANDError("Received unknown error! (Got 0x%02x)" % res)

            print(error_msg)
            return 0

        return 1

    def erase_block(self, page: int):
        "Erase a NAND block."
        if self.nand_id == 1:
            self.write(self.CMD_NAND1_ERASEBLOCK)
        else:
            self.write(self.CMD_NAND0_ERASEBLOCK)

        page_block = page / self.nand_pages_per_block

        # row (page number) address
        self.write(page & 0xFF)
        self.write((page >> 8) & 0xFF)
        self.write((page >> 16) & 0xFF)

        if self.read_result() == 0:
            print(f"Block {page_block} - error erasing block")
            return 0

        return 1

    def readpage(self, page: int):
        "Read data from a NAND page."
        if (self.nand_id == 1):
            self.write(self.CMD_NAND1_READPAGE)
        else:
            self.write(self.CMD_NAND0_READPAGE)

        # address
        # self.write(0x0)
        # self.write(0x0)
        self.write(page & 0xFF)
        self.write((page >> 8) & 0xFF)
        self.write((page >> 16) & 0xFF)

        read_error_code = self.read_result()
        if read_error_code == 0:
            raise NANDError(f"Error while reading page {page}")
        else:
            data = self.read(self.nand_page_size_plus_ras)
            return data

    def writepage(self, page_data: bytes, page_number: int):
        "Write data to a NAND page."
        if len(page_data) != self.nand_page_size_plus_ras:
            print(f"Incorrent data size {len(page_data)}")
            return -1

        if (self.nand_id == 1):
            self.write(self.CMD_NAND1_WRITEPAGE)
        else:
            self.write(self.CMD_NAND0_WRITEPAGE)

        # address
        # self.write(0x0)
        # self.write(0x0)
        self.write(page_number & 0xFF)
        self.write((page_number >> 8) & 0xFF)
        self.write((page_number >> 16) & 0xFF)

        self.write(page_data)

        if self.read_result() == 0:
            return 0

        return 1

    def dump(self, filename: str, block_offset: int, nblocks: int):
        "Dump data from the NAND to a file."

        if nblocks == 0:
            nblocks = self.nand_block_count

        if nblocks > self.nand_block_count:
            nblocks = self.nand_block_count

        with open(filename, "wb") as dumpfile:
            for page in range(block_offset*self.nand_pages_per_block, (block_offset+nblocks)*self.nand_pages_per_block, 1):
                data = self.readpage(page)
                dumpfile.write(data)
                # print "\r%d KB / %d KB"%((page-(block_offset*self.NAND_PAGES_PER_BLOCK)+1)*self.NAND_PAGE_SZ_PLUS_RAS/1024, nblocks*self.NAND_BLOCK_SZ_PLUS_RAS/1024),
                dump_size_progress = (
                    page-(block_offset*self.nand_pages_per_block)+1)*self.nand_page_size_plus_ras/1024
                dump_size_total = nblocks*self.nand_block_size_plus_ras/1024
                print(f"\r{dump_size_progress} KB / {dump_size_total} KB")
                sys.stdout.flush()

    def program_block(self, data: bytes, pgblock: int, verify: bool):
        pagenr = 0

        datasize = len(data)
        if datasize != self.nand_block_size_plus_ras:
            print(
                f"Incorrect length {datasize} != {self.nand_block_size_plus_ras}")
            return -1

        while pagenr < self.nand_pages_per_block:
            real_pagenr = (pgblock * self.nand_pages_per_block) + pagenr
            if pagenr == 0:
                self.erase_block(real_pagenr)

            self.writepage(data[pagenr*self.nand_page_size_plus_ras:(pagenr+1)
                           * self.nand_page_size_plus_ras], real_pagenr)

            pagenr += 1

        # verification
        if verify:
            pagenr = 0
            while pagenr < self.nand_pages_per_block:
                real_pagenr = (pgblock * self.nand_pages_per_block) + pagenr
                if data[pagenr*self.nand_page_size_plus_ras:(pagenr+1)*self.nand_page_size_plus_ras] != self.readpage(real_pagenr):
                    print()
                    # print "Error! Block verification failed. block=0x%x page=%d"%(pgblock, real_pagenr)
                    print(
                        "Error! Block verification failed.",
                        f"block=0x{pgblock:x} page=0x{real_pagenr:x}"
                        )
                    return -1

                pagenr += 1

        return 0

    def program(self, data: bytes, verify: bool, block_offset: int, nblocks: int):
        "Program a NAND chip."
        datasize = len(data)

        if nblocks == 0:
            nblocks = self.nand_block_count - block_offset

        # validate that the data is a multiplication of self.NAND_BLOCK_SZ_PLUS_RAS
        if datasize % self.nand_block_size_plus_ras:
            # print "Error: expecting file size to be a multiplication of block+ras size: %d"%(self.NAND_BLOCK_SZ_PLUS_RAS)
            print(
                f"Error: expecting file size to be a multiplication of block+ras size: {self.nand_block_size_plus_ras}")
            return -1

        # validate that the the user didn't want to read from incorrect place in the file
        if block_offset + nblocks > datasize/self.nand_block_size_plus_ras:
            # print "Error: file is %x bytes long and last block is at %x"%(datasize, (block_offset + nblocks + 1) * self.NAND_BLOCK_SZ_PLUS_RAS)
            print(
                f"Error: file is {datasize:x}  bytes long and last block is at {(block_offset + nblocks + 1) * self.nand_block_size_plus_ras}")
            return -1

        # validate that the the user didn't want to write to incorrect place in the NAND
        if block_offset + nblocks > self.nand_block_count:
            # print "Error: nand has %x blocks. writing outside the nand's capacity"%(self.NAND_NBLOCKS, block_offset + nblocks + 1)
            print(
                f"Error: nand has {self.nand_block_count:x}, writing outside the nand's capacity")
            return -1

        block = 0

        # print "Writing %x blocks to device (starting at offset %x)..."%(nblocks, block_offset)
        print(
            f"Writing {nblocks:x} blocks to device (starting at offset {block_offset:x})...")

        while block < nblocks:
            pgblock = block+block_offset
            self.program_block(data[pgblock*self.nand_block_size_plus_ras:(
                pgblock+1)*self.nand_block_size_plus_ras], pgblock, verify)

            write_progress = ((block+1)*self.nand_block_size_plus_ras)/1024
            write_total = (nblocks*self.nand_block_size_plus_ras)/1024
            print(f"\r{write_progress} KB / {write_total} KB")
            # print "\r%d KB / %d KB"%(((block+1)*self.NAND_BLOCK_SZ_PLUS_RAS)/1024, (nblocks*self.NAND_BLOCK_SZ_PLUS_RAS)/1024),
            sys.stdout.flush()

            block += 1

        print()


def ps3_validate_block(block_data: bytes, page_plus_ras_sz: int, page_sz: int, blocknr: int):
    "Validate a block from a PS3 NAND."
    spare1 = block_data[page_sz:page_plus_ras_sz]
    spare2 = block_data[page_plus_ras_sz+page_sz:page_plus_ras_sz*2]

    if blocknr == 0x1FF:
        return 1

    if spare1[0] != 0xFF or spare2[0] != 0xFF:
        return 0

    return 1


if __name__ == "__main__":
    VERSION_MAJOR = 0
    VERSION_MINOR = 65

    # print "NANDway v%d.%02d - Teensy++ 2.0 NAND Flasher for PS3/Xbox/Wii"%(VERSION_MAJOR, VERSION_MINOR)
    print(
        f"NANDWay v{VERSION_MAJOR}.{VERSION_MINOR:02} - Teensy++ 2.0 NAND Flasher for PS3/Xbox/Wii")
    print("(Original NORway.py by judges <judges@eEcho.com>)")
    print("(Original noralizer.py by Hector Martin \"marcan\" <hector@marcansoft.com>)")
    print()

    if len(sys.argv) == 1:
        print("""
        Usage:
        NANDway.py Serial-Port 0/1 Command

          Serial-Port  Name of serial port to open (eg. COM1, COM2, /dev/ttyACM0, etc)
          0/1  NAND id number: 0-NAND0, 1-NAND1
          Commands:
          *  info
             Displays information about NAND
          *  dump Filename [Offset] [Length]
             Dumps to Filename at [Offset] and [Length]
          *  vwrite/write Filename [Offset] [Length]
             Flashes (v=verify) Filename at [Offset] and [Length]
          *  vdiffwrite/diffwrite Filename Diff-file
             Flashes (v=verify) Filename using a Diff-file
          *  ps3badblocks Filename
             Identifies bad blocks in Filename (raw dump)
          *  bootloader
             Enters Teensy's bootloader mode (for Teensy reprogramming)

             Notes: 1) All offsets and lengths are in hex (number of blocks)
                    2) The Diff-file is a file which lists all the changed
                       offsets of a dump file. This will increase flashing
                       time dramatically.

        Examples:
          NANDway.py COM1 0 info
          NANDway.py COM1 0 dump d:\\myflash.bin
          NANDway.py COM1 1 dump d:\\myflash.bin 3d a0
          NANDway.py COM1 0 write d:\\myflash.bin
          NANDway.py COM3 1 write d:\\myflash.bin 20 1c
          NANDway.py COM3 0 vwrite d:\\myflash.bin
          NANDway.py COM3 1 vwrite d:\\myflash.bin 8d 20
          NANDway.py COM4 0 diffwrite d:\\myflash.bin d:\\myflash_diff.txt
          NANDway.py COM3 1 vdiffwrite d:\\myflash.bin d:\\myflash_diff.txt
          NANDway.py COM1 0 bootloader
          NANDway.py ps3badblocks d:\\myflash.bin
        """)
        sys.exit(0)

    if (len(sys.argv) == 3) and (sys.argv[1] == "ps3badblocks"):
        tStart = time.time()

        with open(sys.argv[2], "rb") as datafile:
            data = datafile.read()

        datasize = len(data)
        page_sz = 2048
        page_plus_ras_sz = 2112
        nblocks = 1024
        pages_per_block = 64
        block = 0
        block_plus_ras_sz = page_plus_ras_sz*pages_per_block
        block_offset = 0

        tStart = time.time()

        while block < nblocks:
            pgblock = block+block_offset

            block_data = data[pgblock*(block_plus_ras_sz):(pgblock+1)*(block_plus_ras_sz)]
            block_valid = ps3_validate_block(
                block_data, page_plus_ras_sz, page_sz, block)
            if block_valid == 0:
                print()
                # print "Invalid block: %d (0x%X)"%(pgblock, pgblock)
                print(f"Invalid block: {pgblock} (0x{pgblock:X})")
                print()

            # print "\r%d KB / %d KB"%(((block+1)*(block_plus_ras_sz))/1024, (nblocks*(block_plus_ras_sz))/1024),
            bblock_progress = ((block+1)*(block_plus_ras_sz))/1024
            bblock_total = (nblocks*(block_plus_ras_sz))/1024
            print(f"\r{bblock_progress} KB / {bblock_total} KB")
            sys.stdout.flush()

            block += 1

        print()
        # print "Done. [%s]"%(datetime.timedelta(seconds=time.time() - tStart))
        print(f"Done. [{datetime.timedelta(seconds=time.time() - tStart)}]")
        sys.exit(0)

    n = NANDFlasher(sys.argv[1], int(sys.argv[2], 10),
                    VERSION_MAJOR, VERSION_MINOR)
    print("Pinging Teensy...")
    freeram = n.ping()
    # print "Available memory: %d bytes"%(freeram)
    print(f"Available memory: {freeram} bytes")
    print()

    tStart = time.time()
    if len(sys.argv) in (5, 6, 7) and sys.argv[3] == "dump":
        n.printstate()
        print()
        print("Dumping...")
        sys.stdout.flush()
        print()

        block_offset = 0
        nblocks = 0

        if len(sys.argv) == 6:
            block_offset = int(sys.argv[5], 16)
        elif len(sys.argv) == 7:
            block_offset = int(sys.argv[5], 16)
            nblocks = int(sys.argv[6], 16)

        n.dump(sys.argv[4], block_offset, nblocks)

        print()
        # print "Done. [%s]"%(datetime.timedelta(seconds=time.time() - tStart))
        print(f"Done. [{datetime.timedelta(seconds=time.time() - tStart)}]")

    if len(sys.argv) == 4 and sys.argv[3] == "info":
        n.printstate()
        print()

    elif len(sys.argv) in (5, 6, 7) and (sys.argv[3] == "write" or sys.argv[3] == "vwrite"):
        n.printstate()
        print()

        print("Writing...")
        sys.stdout.flush()

        print()

        with open(sys.argv[4], "rb") as datafile:
            data = datafile.read()

        block_offset = 0
        nblocks = 0

        if (sys.argv[3] == "vwrite"):
            verify = True
        else:
            verify = False

        if len(sys.argv) == 6:
            block_offset = int(sys.argv[5], 16)
        elif len(sys.argv) == 7:
            block_offset = int(sys.argv[5], 16)
            nblocks = int(sys.argv[6], 16)

        n.program(data, verify, block_offset, nblocks)

        print()
        # print "Done. [%s]"%(datetime.timedelta(seconds=time.time() - tStart))
        print(f"Done. [{datetime.timedelta(seconds=time.time() - tStart)}]")

    elif len(sys.argv) == 6 and (sys.argv[3] == "diffwrite" or sys.argv[3] == "vdiffwrite"):
        n.printstate()
        print()
        print("Writing using diff file ...")
        sys.stdout.flush()
        print()

        with open(sys.argv[4], "rb") as datafile:
            data = datafile.read()
        with open(sys.argv[5], "rb") as difffile:
            diff_data = difffile.readlines()

        block_offset = 0
        nblocks = 0
        nlines = len(diff_data)
        cur_line = 0

        if (sys.argv[3] == "vdiffwrite"):
            verify = True
        else:
            verify = False

        for line in diff_data:
            addr = int(line[2:], 16)
            if addr % n.nand_block_size_plus_ras:
                # print "Error: incorrect address for block addr=%x. addresses must be on a per-block boundary"%(addr)
                print(
                    f"Error: incorrect address for block addr={addr:x}. addresses must be on a per-block boundary")
                sys.exit(0)

            block_offset = int(addr/n.nand_block_size_plus_ras)
            # print "Programming offset %x block %x (%d/%d)"%(addr, block_offset, cur_line+1, nlines)
            print(
                f"Programming offset {addr:x} block {block_offset:x} ({cur_line+1}/{nlines})")
            n.program(data, verify, block_offset, True)
            cur_line += 1

        print()
        # print "Done. [%s]"%(datetime.timedelta(seconds=time.time() - tStart))
        print(f"Done. [{datetime.timedelta(seconds=time.time() - tStart)}]")

    elif len(sys.argv) == 4 and sys.argv[3] == "bootloader":
        print()
        print("Entering Teensy's bootloader mode... Goodbye!")
        n.bootloader()
        sys.exit(0)

    n.ping()
