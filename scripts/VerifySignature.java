import com.android.apksig.ApkVerifier;
import java.io.File;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.security.cert.Certificate;
import java.util.HexFormat;
import java.util.jar.JarFile;

class VerifySignature {
    public static void main(String[] args) throws Exception {
        File file = new File(args[0]);
        Certificate certificate;
        if (file.getName().endsWith(".apk")) {
            var result = new ApkVerifier.Builder(file).setMinCheckedPlatformVersion(26).build().verify();
            if (!result.isVerified() || result.getSignerCertificates().size() != 1) {
                throw new SecurityException("Invalid APK signature: " + result.getErrors());
            }
            certificate = result.getSignerCertificates().get(0);
        } else {
            certificate = null;
            try (var jar = new JarFile(file, true)) {
                var entries = jar.entries();
                while (entries.hasMoreElements()) {
                    var entry = entries.nextElement();
                    if (entry.isDirectory() || entry.getName().startsWith("META-INF/")) continue;
                    try (var input = jar.getInputStream(entry)) {
                        input.transferTo(OutputStream.nullOutputStream());
                    }
                    var certificates = entry.getCertificates();
                    if (certificates == null || certificates.length != 1) {
                        throw new SecurityException("Unsigned JAR entry: " + entry.getName());
                    }
                    if (certificate != null && !certificate.equals(certificates[0])) {
                        throw new SecurityException("Multiple JAR signers");
                    }
                    certificate = certificates[0];
                }
            }
            if (certificate == null) throw new SecurityException("Empty signed JAR");
        }
        System.out.println(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded())));
    }
}
