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

import serial, time, datetime, sys, struct

class TeensySerialError(Exception):
	pass

class TeensySerial(object):
	BUFSIZE = 32768

	def __init__(self, port):
		self.ser = serial.Serial(port, 9600, timeout=300, rtscts=False, dsrdtr=False, xonxoff=False, write_timeout=120)
		if self.ser is None:
			raise TeensySerialError(f"could not open serial {port}")
		self.ser.reset_input_buffer()
		self.ser.reset_output_buffer()
		self.obuf: bytearray = bytearray()

	def write(self, s):
		if isinstance(s,int):
			self.obuf.append(s)
		elif isinstance(s,tuple) or isinstance(s,list):
			self.obuf.extend(s)
		while len(self.obuf) > self.BUFSIZE:
			self.ser.write(self.obuf[:self.BUFSIZE])
			self.obuf = self.obuf[self.BUFSIZE:]

	def flush(self):
		if len(self.obuf):
			self.ser.write(self.obuf)
			self.ser.flush()
			self.obuf.clear()

	def read(self, size):
		self.flush()
		data = self.ser.read(size)
		return data

	def readbyte(self):
		return ord(self.read(1))

	def close(self):
		print()
		print("Closing serial device...")
		if self.ser is None:
			print("Device already closed.")
		else:
			self.ser.close()
			print("Done.")

class NANDError(Exception):
	pass

class NANDFlasher(TeensySerial):
	VERSION_MAJOR = 0
	VERSION_MINOR = 0
	NAND_ID = 0
	NAND_DISABLE_PULLUPS = 0
	MF_ID = 0
	DEVICE_ID = 0
	NAND_PAGE_SZ = 0
	NAND_RAS = 0 # Redundent Area Size
	NAND_PAGE_SZ_PLUS_RAS = 0
	NAND_NPAGES = 0
	NAND_NBLOCKS = 0
	NAND_PAGES_PER_BLOCK = 0
	NAND_BLOCK_SZ = 0
	NAND_BLOCK_SZ_PLUS_RAS = 0
	NAND_BUS_WIDTH = 0
	NAND_NPLANES = 0
	NAND_PLANE_SZ = 0

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
	nand_names = {
		0xEC: { # Samsung
			"vendor_name": "Samsung",
			0xA1: "K9F1G08R0A",
			0XD5: "K9GAG08U0M",
			0xF1: "K9F1G08U0A",
			0x79: "K9T1G08U0M",
			0xDA: "K9F2G08U0M"
		},
		0xAD: { # Hynix (oh no)
			"vendor_name": "Hynix",
			0x73: "HY27US08281A",
			0xD7: "H27UBG8T2A",
			0xDA: "HY27UF082G2B",
			0xDC: "H27U4G8F2D"
		},
		0x98: { # Toshiba
			"vendor_name": "Toshiba",
			0xDC: "TC58NVG2S3E"
		}
	}


	def __init__(self, port, nand_id, ver_major, ver_minor):
		if port:
			TeensySerial.__init__(self, port)
		self.NAND_ID = nand_id & 1
		self.NAND_DISABLE_PULLUPS = nand_id & 10
		self.VERSION_MAJOR = ver_major
		self.VERSION_MINOR = ver_minor

	def ping(self):
		self.write(self.CMD_PING1)
		self.write(self.CMD_PING2)
		ver_major = self.readbyte()
		ver_minor = self.readbyte()
		freeram = (self.readbyte() << 8) | self.readbyte()
		if (ver_major != self.VERSION_MAJOR) or (ver_minor != self.VERSION_MINOR):
			# print "Ping failed (expected v%d.%02d, got v%d.%02d)"%(self.VERSION_MAJOR, self.VERSION_MINOR, ver_major, ver_minor)
			print(f"Ping failed (expected v{self.VERSION_MAJOR}.{self.VERSION_MINOR:02}, got {ver_major}.{ver_minor:02})")
			self.close()
			sys.exit(1)

		return freeram

	def readid(self):
		if (self.NAND_DISABLE_PULLUPS == 0):
			self.write(self.CMD_PULLUPS_ENABLE)
		else:
			self.write(self.CMD_PULLUPS_DISABLE)

		if (self.NAND_ID == 1):
			self.write(self.CMD_NAND1_ID)
		else:
			self.write(self.CMD_NAND0_ID)

		isCommandSupported = self.readbyte()
		if (isCommandSupported != 89): #'Y'
			print()
			print("NAND_ID 1 not supported for Signal Booster Edition! Exiting...")
			self.close()
			sys.exit(1)

		nand_info = self.read(25)
		
		#print "%x, %x, %x, %x, %x"%(self.MF_ID, self.DEVICE_ID, info1, info, info3)
		#print "Raw ID data: 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x"%(ord(nand_info[0]), ord(nand_info[1]), ord(nand_info[2]), ord(nand_info[3]), ord(nand_info[4]))
		print("Raw ID info:", ' '.join(f"0x{byte:02x}" for byte in nand_info[0:5]))
		
		self.MF_ID = nand_info[0]
		self.DEVICE_ID = nand_info[1]
		self.NAND_PAGE_SZ = (nand_info[5] << 24) | (nand_info[6] << 16) | (nand_info[7] << 8) | nand_info[8]
		self.NAND_RAS = (nand_info[9] << 8) | nand_info[10]
		self.NAND_BUS_WIDTH = nand_info[11]
		self.NAND_BLOCK_SZ = (nand_info[12] << 24) | (nand_info[13] << 16) | (nand_info[14] << 8) | nand_info[15]
		self.NAND_NBLOCKS = (nand_info[16] << 24) | (nand_info[17] << 16) | (nand_info[18] << 8) | nand_info[19]
		self.NAND_NPLANES = nand_info[20]
		self.NAND_PLANE_SZ = (nand_info[21] << 24) | (nand_info[22] << 16) | (nand_info[23] << 8) | nand_info[24]

		if (self.NAND_PAGE_SZ <= 0):
			print()
			print("Error reading size of NAND! Exiting...")
			self.close()
			sys.exit(1)
		if (self.NAND_BUS_WIDTH != 8):
			print()
			print("Only 8-bit NANDs are supported! Exiting...")
			self.close()
			sys.exit(1)
		if (self.MF_ID == 0):
			print()
			print("Unknown chip manufacturer! Exiting...")
			self.close()
			sys.exit(1)
		if (self.DEVICE_ID == 0):
			print()
			print("Unknown device id! Exiting...")
			self.close()
			sys.exit(1)

		if self.MF_ID == 0x98 and self.DEVICE_ID == 0xdc:
			# TC58NVG2S3E
			self.NAND_NBLOCKS = self.NAND_NBLOCKS // 4
			self.NAND_PLANE_SZ = self.NAND_PLANE_SZ // 4

		self.NAND_PAGES_PER_BLOCK = self.NAND_BLOCK_SZ / self.NAND_PAGE_SZ
		self.NAND_PAGE_SZ_PLUS_RAS = self.NAND_PAGE_SZ + self.NAND_RAS
		self.NAND_NPAGES = self.NAND_PAGES_PER_BLOCK * self.NAND_NBLOCKS
		self.NAND_BLOCK_SZ_PLUS_RAS = self.NAND_PAGES_PER_BLOCK * self.NAND_PAGE_SZ_PLUS_RAS
			
	def printstate(self):
		# print "NAND%d information:"%self.NAND_ID
		print(f"NAND{self.NAND_ID} information:")
		self.readid()

		print()
		if self.MF_ID in self.nand_names:
			mfg_name = self.nand_names[self.MF_ID]['vendor_name']
			nand_name = self.nand_names[self.MF_ID].get(self.DEVICE_ID, "Unknown")
			print(f"NAND chip manufacturer: {mfg_name} (0x{self.MF_ID:02x})")
			print(f"NAND chip type:        {nand_name} (0x{self.DEVICE_ID:02x})")
		else:
			print(f"NAND chip manufacturer: unknown (0x{self.MF_ID:02x})")
			print(f"NAND chip type:        unknown (0x{self.DEVICE_ID:02x})")

		print(f"""
		NAND size:              {self.NAND_BLOCK_SZ * self.NAND_NBLOCKS / 1024 / 1024} MB
		NAND plus RAS size:     {self.NAND_BLOCK_SZ_PLUS_RAS * self.NAND_NBLOCKS / 1024 / 1024} MB
		Page size:              {self.NAND_PAGE_SZ} bytes
		Page plus RAS size:     {self.NAND_PAGE_SZ_PLUS_RAS} bytes
		Block size:             {self.NAND_BLOCK_SZ} bytes
		Block plus RAS size:    {self.NAND_BLOCK_SZ_PLUS_RAS} bytes
		RAS size:               {self.NAND_RAS} bytes
		Plane size:             {self.NAND_PLANE_SZ}
		Pages per block:        {self.NAND_PAGES_PER_BLOCK}
		Number of blocks:       {self.NAND_NBLOCKS}
		Number of pages:        {self.NAND_NPAGES}
		Number of planes:       {self.NAND_NPLANES}
		Bus width:              {self.NAND_BUS_WIDTH}-bit
		""")

	def bootloader(self):
		self.write(self.CMD_BOOTLOADER)
		self.flush()

	def read_result(self):
		# read status byte
		res = self.readbyte()
		
		# 'K' = okay, 'T' = timeout error when writing, 'R' = Teensy receive buffer timeout, 'V' = Verification error
		error_msg = ""
		
		if (res != 75): #'K'
			if (res == 84): #'T'
				error_msg = "RY/BY timeout error while writing!"
			elif (res == 82): #'R'
				self.close()
				raise NANDError("Teensy receive buffer timeout! Disconnect and reconnect Teensy!")
			elif (res == 86): #'V'
				error_msg = "Verification error!"
			elif (res == 80): #'P'
				error_msg = "Device is write-protected!"
			else:
				self.close()
				raise NANDError("Received unknown error! (Got 0x%02x)"%res)

			print(error_msg)
			return 0

		return 1

	def erase_block(self, pagenr):
		if (self.NAND_ID == 1):
			self.write(self.CMD_NAND1_ERASEBLOCK)
		else:
			self.write(self.CMD_NAND0_ERASEBLOCK)

		pgblock = pagenr / self.NAND_PAGES_PER_BLOCK
		
		# row (page number) address
		self.write(pagenr & 0xFF)
		self.write((pagenr >> 8) & 0xFF)
		self.write((pagenr >> 16) & 0xFF)

		if self.read_result() == 0:
			print(f"Block {pgblock} - error erasing block")
			return 0

		return 1

	def readpage(self, page):
		if (self.NAND_ID == 1):
			self.write(self.CMD_NAND1_READPAGE)
		else:
			self.write(self.CMD_NAND0_READPAGE)

		# address
		#self.write(0x0)
		#self.write(0x0)
		self.write(page & 0xFF)
		self.write((page >> 8) & 0xFF)
		self.write((page >> 16) & 0xFF)
		
		if self.read_result() == 0:
			return "error"
		
		data = self.read(self.NAND_PAGE_SZ_PLUS_RAS)
		return data
		
	def writepage(self, data, pagenr):
		if len(data) != self.NAND_PAGE_SZ_PLUS_RAS:
			print(f"Incorrent data size {len(data)}")
			return -1
			
		pgblock = pagenr / self.NAND_PAGES_PER_BLOCK
		pgoff = pagenr % self.NAND_PAGES_PER_BLOCK
		
		if (self.NAND_ID == 1):
			self.write(self.CMD_NAND1_WRITEPAGE)
		else:
			self.write(self.CMD_NAND0_WRITEPAGE)

		# address
		#self.write(0x0)
		#self.write(0x0)
		self.write(pagenr & 0xFF)
		self.write((pagenr >> 8) & 0xFF)
		self.write((pagenr >> 16) & 0xFF)

		self.write(data)
		
		if self.read_result() == 0:
			return 0
		
		return 1

	def dump(self, filename: str, block_offset: int, nblocks: int):

		if nblocks == 0:
			nblocks = self.NAND_NBLOCKS

		if nblocks > self.NAND_NBLOCKS:
			nblocks = self.NAND_NBLOCKS
		
		with open(filename, "wb") as dumpfile:
			range_start = block_offset*self.NAND_PAGES_PER_BLOCK
			range_end = (block_offset+nblocks)*self.NAND_PAGES_PER_BLOCK
			if range_start != int(range_start) or range_end != int(range_end):
				print("!! floating point has gone wrong !!")
				print(f"show this to the dev: start {range_start} end {range_end}")
			for page in range(int(range_start), int(range_end)):
				data = self.readpage(page)
				dumpfile.write(data)
				# print "\r%d KB / %d KB"%((page-(block_offset*self.NAND_PAGES_PER_BLOCK)+1)*self.NAND_PAGE_SZ_PLUS_RAS/1024, nblocks*self.NAND_BLOCK_SZ_PLUS_RAS/1024),
				dump_size_progress = (page-(block_offset*self.NAND_PAGES_PER_BLOCK)+1)*self.NAND_PAGE_SZ_PLUS_RAS/1024
				dump_size_total = nblocks*self.NAND_BLOCK_SZ_PLUS_RAS/1024
				print(f"\r{dump_size_progress} KB / {dump_size_total} KB")
				sys.stdout.flush()

		return

	def program_block(self, data, pgblock, verify):
		pagenr = 0
		
		datasize = len(data)
		if datasize != self.NAND_BLOCK_SZ_PLUS_RAS:
			print(f"Incorrect length {datasize} != {self.NAND_BLOCK_SZ_PLUS_RAS}")
			return -1
		
		while pagenr < self.NAND_PAGES_PER_BLOCK:
			real_pagenr = (pgblock * self.NAND_PAGES_PER_BLOCK) + pagenr
			if pagenr == 0:
				self.erase_block(real_pagenr)

			self.writepage(data[pagenr*self.NAND_PAGE_SZ_PLUS_RAS:(pagenr+1)*self.NAND_PAGE_SZ_PLUS_RAS], real_pagenr)
				
			pagenr += 1

		# verification
		if verify == 1:
			pagenr = 0;
			while pagenr < self.NAND_PAGES_PER_BLOCK:
				real_pagenr = (pgblock * self.NAND_PAGES_PER_BLOCK) + pagenr
				if data[pagenr*self.NAND_PAGE_SZ_PLUS_RAS:(pagenr+1)*self.NAND_PAGE_SZ_PLUS_RAS] != self.readpage(real_pagenr):
					print()
					# print "Error! Block verification failed. block=0x%x page=%d"%(pgblock, real_pagenr)
					print(f"Error! Block verification failed. block=0x{pgblock:x} page=0x{real_pagenr:x}")
					return  -1
					
				pagenr += 1
				
		return 0

	def program(self, data, verify, block_offset, nblocks):
		datasize = len(data)

		if nblocks == 0:
			nblocks = self.NAND_NBLOCKS - block_offset
			
		# validate that the data is a multiplication of self.NAND_BLOCK_SZ_PLUS_RAS
		if datasize % self.NAND_BLOCK_SZ_PLUS_RAS:
			# print "Error: expecting file size to be a multiplication of block+ras size: %d"%(self.NAND_BLOCK_SZ_PLUS_RAS)
			print(f"Error: expecting file size to be a multiplication of block+ras size: {self.NAND_BLOCK_SZ_PLUS_RAS}")
			return -1

		# validate that the the user didn't want to read from incorrect place in the file
		if block_offset + nblocks > datasize/self.NAND_BLOCK_SZ_PLUS_RAS:
			# print "Error: file is %x bytes long and last block is at %x"%(datasize, (block_offset + nblocks + 1) * self.NAND_BLOCK_SZ_PLUS_RAS)
			print(f"Error: file is {datasize:x}  bytes long and last block is at {(block_offset + nblocks + 1) * self.NAND_BLOCK_SZ_PLUS_RAS}")
			return -1
		
		# validate that the the user didn't want to write to incorrect place in the NAND
		if block_offset + nblocks > self.NAND_NBLOCKS:
			#print "Error: nand has %x blocks. writing outside the nand's capacity"%(self.NAND_NBLOCKS, block_offset + nblocks + 1)
			print(f"Error: nand has {self.NAND_NBLOCKS:x}, writing outside the nand's capacity")
			return -1
		
		block = 0

		#print "Writing %x blocks to device (starting at offset %x)..."%(nblocks, block_offset)
		print(f"Writing {nblocks:x} blocks to device (starting at offset {block_offset:x})...")
		
		while block < nblocks:
			pgblock = block+block_offset
			data_index_start = pgblock*self.NAND_BLOCK_SZ_PLUS_RAS
			data_index_end = (pgblock+1)*self.NAND_BLOCK_SZ_PLUS_RAS
			if data_index_start != int(data_index_start) or data_index_end != int(data_index_end):
				print("!! floating point has gone wrong !!")
				print(f"show this to the dev: data index start {data_index_start} end {data_index_end}")
			self.program_block(data[int(data_index_start):int(data_index_end)], pgblock, verify)

			write_progress = ((block+1)*self.NAND_BLOCK_SZ_PLUS_RAS)/1024
			write_total = (nblocks*self.NAND_BLOCK_SZ_PLUS_RAS)/1024
			print(f"\r{write_progress} KB / {write_total} KB")
			# print "\r%d KB / %d KB"%(((block+1)*self.NAND_BLOCK_SZ_PLUS_RAS)/1024, (nblocks*self.NAND_BLOCK_SZ_PLUS_RAS)/1024),
			sys.stdout.flush()

			block += 1

		print()
		
def ps3_validate_block(block_data, page_plus_ras_sz, page_sz, blocknr):
	spare1 = block_data[page_sz:page_plus_ras_sz]
	spare2 = block_data[page_plus_ras_sz+page_sz:page_plus_ras_sz*2]
	
	if blocknr == 0x1FF:
		return 1

	if ord(spare1[0]) != 0xFF or ord(spare2[0]) != 0xFF:
		return 0
		
	return 1


if __name__ == "__main__":
	VERSION_MAJOR = 0
	VERSION_MINOR = 65

	# print "NANDway v%d.%02d - Teensy++ 2.0 NAND Flasher for PS3/Xbox/Wii"%(VERSION_MAJOR, VERSION_MINOR)
	print(f"NANDWay v{VERSION_MAJOR}.{VERSION_MINOR:02} - Teensy++ 2.0 NAND Flasher for PS3/Xbox/Wii")
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
		  NANDway.py COM1 0 dump d:\myflash.bin
		  NANDway.py COM1 1 dump d:\myflash.bin 3d a0
		  NANDway.py COM1 0 write d:\myflash.bin
		  NANDway.py COM3 1 write d:\myflash.bin 20 1c
		  NANDway.py COM3 0 vwrite d:\myflash.bin
		  NANDway.py COM3 1 vwrite d:\myflash.bin 8d 20
		  NANDway.py COM4 0 diffwrite d:\myflash.bin d:\myflash_diff.txt
		  NANDway.py COM3 1 vdiffwrite d:\myflash.bin d:\myflash_diff.txt
		  NANDway.py COM1 0 bootloader
		  NANDway.py ps3badblocks d:\myflash.bin
		""")
		sys.exit(0)

	if (len(sys.argv) == 3) and (sys.argv[1] == "ps3badblocks"):
		tStart = time.time()

		with open(sys.argv[2],"rb") as datafile:
			data = datafile.read()

		datasize = len(data)
		page_sz = 2048
		page_plus_ras_sz = 2112
		nblocks = 1024
		pages_per_block = 64
		block = 0
		block_plus_ras_sz=page_plus_ras_sz*pages_per_block
		block_offset=0
		
		tStart = time.time()
		
		while block < nblocks:
			pgblock = block+block_offset

			block_data=data[pgblock*(block_plus_ras_sz):(pgblock+1)*(block_plus_ras_sz)]
			block_valid = ps3_validate_block(block_data, page_plus_ras_sz, page_sz, block)
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
		
	n = NANDFlasher(sys.argv[1], int(sys.argv[2], 10), VERSION_MAJOR, VERSION_MINOR)
	print("Pinging Teensy...")
	freeram = n.ping()
	# print "Available memory: %d bytes"%(freeram)
	print(f"Available memory: {freeram} bytes")
	print
	
	tStart = time.time()
	if len(sys.argv) in (5,6,7) and sys.argv[3] == "dump":
		n.printstate()
		print()
		print("Dumping..."),
		sys.stdout.flush()
		print()
		
		block_offset=0
		nblocks=0

		if len(sys.argv) == 6:
			block_offset=int(sys.argv[5],16)
		elif len(sys.argv) == 7:
			block_offset=int(sys.argv[5],16)
			nblocks=int(sys.argv[6],16)

		n.dump(sys.argv[4], block_offset, nblocks)
		
		print()
		# print "Done. [%s]"%(datetime.timedelta(seconds=time.time() - tStart))
		print(f"Done. [{datetime.timedelta(seconds=time.time() - tStart)}]")

			
	if len(sys.argv) == 4 and sys.argv[3] == "info":
		n.printstate()
		print()
			
	elif len(sys.argv) in (5,6,7) and (sys.argv[3] == "write" or sys.argv[3] == "vwrite"):
		n.printstate()
		print()
		
		print("Writing...")
		sys.stdout.flush()

		print()
		
		with open(sys.argv[4],"rb") as datafile:
			data = datafile.read()

		block_offset=0
		nblocks=0
		verify=0

		if (sys.argv[3] == "vwrite"):
			verify=1
		
		if len(sys.argv) == 6:
			block_offset=int(sys.argv[5],16)
		elif len(sys.argv) == 7:
			block_offset=int(sys.argv[5],16)
			nblocks=int(sys.argv[6],16)

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
		
		with open(sys.argv[4],"rb") as datafile:
			data = datafile.read()
		with open(sys.argv[5],"rb") as difffile:
			diff_data = difffile.read()

		block_offset=0
		nblocks=0
		verify=0
		nlines=len(diff_data)
		cur_line=0

		if (sys.argv[3] == "vdiffwrite"):
			verify=1
		
		for line in diff_data:
			addr=int(line[2:], 16)
			if addr % n.NAND_BLOCK_SZ_PLUS_RAS:
				# print "Error: incorrect address for block addr=%x. addresses must be on a per-block boundary"%(addr)
				print(f"Error: incorrect address for block addr={addr:x}. addresses must be on a per-block boundary")
				sys.exit(0)

			block_offset=addr/n.NAND_BLOCK_SZ_PLUS_RAS
			# print "Programming offset %x block %x (%d/%d)"%(addr, block_offset, cur_line+1, nlines)
			print(f"Programming offset {addr:x} block {block_offset:x} ({cur_line+1}/{nlines})")
			n.program(data, verify, block_offset, 1)
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
