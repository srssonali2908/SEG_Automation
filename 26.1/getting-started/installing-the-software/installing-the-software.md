# Installing the Software

Install the product on a supported host.

**Before you begin**

Make sure you have administrator rights.

The installer is described in [Introduction](../../introduction.md#overview).

1. Run the installer.

    ```bash
    ./setup.sh --accept-eula
    ./setup.sh --prefix /opt/smoke
    ```

2. Review the block diagram.

    ![System block diagram](../../assets/block-diagram.png)

    *Block diagram*

3. Verify the install.

    > [!NOTE]
    > **Tip:** Run the command twice if the first run is slow.

    1. Open a terminal.
    2. Run `smoke --version`.

**Result**

The product is installed.
