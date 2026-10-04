// An offline TDLib JSON query using Go's built-in C interoperability.
package main

/*
#cgo CFLAGS: -I/usr/local/include
#cgo LDFLAGS: -L/usr/local/lib -ltdjson
#include <stdlib.h>
#include <td/telegram/td_json_client.h>
*/
import "C"

import (
	"fmt"
	"unsafe"
)

func main() {
	request := C.CString(`{"@type":"getOption","name":"version"}`)
	defer C.free(unsafe.Pointer(request))
	result := C.td_execute(request)
	if result == nil {
		panic("TDLib did not return a synchronous response")
	}
	// TDLib owns the result pointer. Copy it before the next execute call.
	fmt.Println(C.GoString(result))
}
