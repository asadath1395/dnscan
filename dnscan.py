#!/usr/bin/env python
#
# dnscan copyright (C) 2013 rbsec
# Licensed under GPLv3, see LICENSE for details
#

import argparse
import Queue
import sys
import threading

try:
    import dns.query
    import dns.resolver
    import dns.zone
except:
    print "FATAL: Module dnspython missing (python-dnspython)"
    sys.exit(1)

# Usage: dnscan.py <domain name> <wordlist>

class scanner(threading.Thread):
    def __init__(self, queue):
        global wildcard
        threading.Thread.__init__(self)
        self.queue = queue

    def get_name(self, domain):
            global wildcard
            try:
                if sys.stdout.isatty():
                    sys.stdout.write(domain + "                              \r")
                    sys.stdout.flush()
                res = lookup(domain)
                for rdata in res:
                    if wildcard:
                        if rdata.address == wildcard:
                            return
                    print rdata.address + " - " + domain
                if domain != target:    # Don't scan root domain twice
                    add_target(domain)  # Recursively scan subdomains
            except:
                pass

    def run(self):
        while True:
            try:
                domain = self.queue.get(timeout=1)
            except:
                return
            self.get_name(domain)
            self.queue.task_done()


class output:
    def status(self, message):
        print col.blue + "[*] " + col.end + message

    def good(self, message):
        print col.green + "[+] " + col.end + message

    def verbose(self, message):
        if args.verbose:
            print col.brown + "[v] " + col.end + message

    def warn(self, message):
        print col.red + "[-] " + col.end + message

    def fatal(self, message):
        print col.red + "FATAL: " + col.end + message


class col:
    if sys.stdout.isatty():
        green = '\033[32m'
        blue = '\033[94m'
        red = '\033[31m'
        brown = '\033[33m'
        end = '\033[0m'
    else:
        green = ""
        blue = ""
        red = ""
        brown = ""
        end = ""


def lookup(domain):
    try:
        res = resolver.query(domain, 'A')
        return res
    except:
        return

def get_wildcard(target):
    res = lookup("nonexistantdomain" + "." + target)
    if res:
        out.good("Wildcard domain found - " + res[0].address)
        return res[0].address
    else:
        out.good("No wildcard domain found")

def get_nameservers(target):
    try:
        ns = resolver.query(target, 'NS')
        return ns
    except:
        return

def zone_transfer(domain, ns):
    out.good("Trying zone transfer against " + str(ns))
    try:
        zone = dns.zone.from_xfr(dns.query.xfr(str(ns), domain, relativize=False),
                                 relativize=False)
        out.good("Zone transfer sucessful")
        names = zone.nodes.keys()
        names.sort()
        for n in names:
            print zone[n].to_text(n)    # Print raw zone
        sys.exit()
    except Exception, e:
        pass

def add_target(domain):
    for word in wordlist:
        queue.put(word + "." + domain)

def get_args():
    global args
    
    parser = argparse.ArgumentParser('dnscan.py', formatter_class=lambda prog:argparse.HelpFormatter(prog,max_help_position=40))
    parser.add_argument('-d', '--domain', help='Target domain', dest='domain', required=True)
    parser.add_argument('-w', '--wordlist', help='Wordlist', dest='wordlist', required=True)
    parser.add_argument('-t', '--threads', help='Number of threads', dest='threads', required=False, type=int, default=8)
    parser.add_argument('-v', '--verbose', action="store_true", default=False, help='Verbose mode', dest='verbose', required=False)
    args = parser.parse_args()

def setup():
    global target, wordlist, queue, resolver
    target = args.domain
    try:
        wordlist = open(args.wordlist).read().splitlines()
    except:
        out.fatal("Could not open wordlist " + args.wordlist)
        sys.exit(1)

    # Number of threads should be between 1 and 32
    if args.threads < 1:
        args.threads = 1
    elif args.threads > 32:
        args.threads = 32
    queue = Queue.Queue()
    resolver = dns.resolver.Resolver()
    resolver.timeout = 1


if __name__ == "__main__":
    global wildcard
    out = output()
    get_args()
    setup()

    nameservers = get_nameservers(target)
    targetns = []       # NS servers for target
    for ns in nameservers:
        ns = str(ns)[:-1]   # Removed trailing dot
        res = lookup(ns)
        for rdata in res:
            targetns.append(rdata.address)
        zone_transfer(target, ns)
#    resolver.nameservers = targetns     # Use target's NS servers for lokups
# Missing results using domain's NS - removed for now
    out.warn("Zone transfer failed")

    wildcard = get_wildcard(target)
    out.status("Scanning " + target)
    queue.put(target)   # Add actual domain as well as subdomains
    add_target(target)

    for i in range(args.threads):
        t = scanner(queue)
        t.setDaemon(True)
        t.start()
    try:
        for i in range(args.threads):
            t.join(1024)       # Timeout needed or threads ignore exceptions
    except KeyboardInterrupt:
        out.fatal("Quitting...")
