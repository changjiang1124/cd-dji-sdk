/*
 ********************************************************************
 *
 * @copyright (c) 2023 DJI. All rights reserved.
 *
 * All information contained herein is, and remains, the property of DJI.
 * The intellectual and technical concepts contained herein are proprietary
 * to DJI and may be covered by U.S. and foreign patents, patents in process,
 * and protected by trade secret or copyright law.  Dissemination of this
 * information, including but not limited to data and other proprietary
 * material(s) incorporated within the information, in any form, is strictly
 * prohibited without the express written consent of DJI.
 *
 * If you receive this source code without DJI’s authorization, you may not
 * further disseminate the information, and you must immediately remove the
 * source code and notify DJI of its removal. DJI reserves the right to pursue
 * legal actions against you for any loss(es) or damage(s) caused by your
 * failure to do so.
 *
 *********************************************************************
 */
#include "key_store_default.h"
#include <unistd.h>

#include <memory>

#include "init.h"
#include "openssl/rsa.h"

namespace edge_sdk {

namespace {
std::shared_ptr<std::string> rsa2048_public_key_;
std::shared_ptr<std::string> rsa2048_private_key_;

// 改成你的测试路径
const char* kPathPublicKey  = "/home/celestial/dev/esdk-test/keystore/public.der";
const char* kPathPrivateKey = "/home/celestial/dev/esdk-test/keystore/private.der";
}  // namespace

KeyStoreDefault::KeyStoreDefault() {
    if (!ReadKeys()) {
        printf("ERROR: cannot read DER keys from keystore\n");
    }
}

// 修正判断对象（之前写反了）
ErrorCode KeyStoreDefault::RSA2048_GetDERPrivateKey(std::string& private_key) const {
    if (!rsa2048_private_key_ || rsa2048_private_key_->empty()) {
        return kErrorParamGetFailure;
    }
    private_key = *rsa2048_private_key_;
    return kOk;
}
ErrorCode KeyStoreDefault::RSA2048_GetDERPublicKey(std::string& public_key) const {
    if (!rsa2048_public_key_ || rsa2048_public_key_->empty()) {
        return kErrorParamGetFailure;
    }
    public_key = *rsa2048_public_key_;
    return kOk;
}

static bool ReadAll(const char* path, std::string& out) {
    FILE* f = fopen(path, "rb");
    if (!f) return false;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return false; }
    long n = ftell(f);
    if (n <= 0) { fclose(f); return false; }
    rewind(f);
    out.resize(static_cast<size_t>(n));
    size_t r = fread(&out[0], 1, out.size(), f);
    fclose(f);
    return r == out.size();
}

bool KeyStoreDefault::ReadKeys() {
    std::string pub, priv;
    if (!ReadAll(kPathPublicKey, pub)) {
        printf("ERROR: read public.der failed: %s\n", kPathPublicKey);
        return false;
    }
    if (!ReadAll(kPathPrivateKey, priv)) {
        printf("ERROR: read private.der failed: %s\n", kPathPrivateKey);
        return false;
    }
    rsa2048_public_key_  = std::make_shared<std::string>(std::move(pub));
    rsa2048_private_key_ = std::make_shared<std::string>(std::move(priv));
    return true;
}



}  // namespace edge_sdk

