{pkgs}: {
  deps = [
    pkgs.postgresql
    pkgs.openssl
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
  ];
}
