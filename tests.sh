#!/bin/bash

cd /tests
TEST_CMD=${TEST_CMD:-pytest}
$TEST_CMD
