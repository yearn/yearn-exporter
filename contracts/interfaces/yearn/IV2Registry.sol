// SPDX-License-Identifier: MIT

pragma solidity 0.8.4;

interface IV2Registry {
  function wrappedVaults(address _vault) external view returns (address);

  function isDelegatedVault(address _vault) external view returns (bool);

  // Vaults getters
  function getVault(uint256 index) external view returns (address vault);

  function getVaults() external view returns (address[] memory);

  function numTokens() external view returns (uint256 _numTokens);

  function tokens(uint256 _index) external view returns (address _token);

  function vaults(address _token, uint256 _index) external view returns (address _vault);

  function getVaultInfo(address _vault)
    external
    view
    returns (
      address controller,
      address token,
      address strategy,
      bool isWrapped,
      bool isDelegated
    );

  function getVaultsInfo()
    external
    view
    returns (
      address[] memory controllerArray,
      address[] memory tokenArray,
      address[] memory strategyArray,
      bool[] memory isWrappedArray,
      bool[] memory isDelegatedArray
    );
}