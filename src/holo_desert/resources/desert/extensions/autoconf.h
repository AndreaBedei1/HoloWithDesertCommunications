// Build-only compatibility header for the pinned official linux/amd64 image.
// The distribution retains NS source headers but removes generated autoconf.h.
// These are Linux LP64 feature macros, including the three explicit settings
// appended by DESERT_Framework/Installer/installDESERT_LOCAL.sh::build_NS.
// No simulator implementation or installed upstream source file is changed.
#pragma once
#include <cstdint>
#include <string>
#include <unistd.h>
#define RANDOM_RETURN_TYPE long
#define HAVE_STL 1
#define CPP_REQUIRES_NAMESPACE 1
#define HAVE_INT64 1
#define SIZEOF_LONG 8
#define HAVE_SOCKLEN_T 1
#define STDC_HEADERS 1
#define HAVE_BCOPY 1
#define HAVE_BZERO 1
#define HAVE_GETRUSAGE 1
#define HAVE_SBRK 1
#define HAVE_SNPRINTF 1
#define HAVE_STRTOLL 1
#define HAVE_STRING_H 1
#define HAVE_STRINGS_H 1
#define HAVE_ARPA_INET_H 1
#define HAVE_NETINET_IN_H 1
#define HAVE_UNISTD_H 1
#define HAVE_TIME_H 1
using namespace std;
static_assert(sizeof(long) == 8 && sizeof(void*) == 8, "Pinned NS ABI requires Linux LP64");
