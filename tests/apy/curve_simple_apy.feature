Feature: Curve APY calculation
    Scenario: Calculating curve simple
        Given I set the date to '2022-04-06'
        And I calculate the APY for the vault <address>
        Then the type should be <type>
        And the gross_apr should be <gross_apr>
        And the net_apy should be <net_apy>

        Examples:
        | address                                     | type  | gross_apr           | net_apy             |
        | 0xdCD90C7f6324cfa40d7169ef80b12031770B4325  | crv   | 0.05737093451761255 | 0.050058512767167204|
        | 0x27b7b1ad7288079A66d12350c828D3C00A6F07d7  | crv   | 0.11176129880725783 | 0.0691230850636729  |
