terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.20" }
  }
}

provider "azurerm" {
  features {}
  # Validate only. Nothing in CI runs plan or apply; see docs/deploy.md for the gated manual path.
}
