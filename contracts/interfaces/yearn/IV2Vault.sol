// SPDX-License-Identifier: MIT

pragma solidity 0.8.4;

interface IV2Vault {
  function withdrawalQueue(uint256 _index) external view returns (address _strategy);
}